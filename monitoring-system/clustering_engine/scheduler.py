import json
import logging
import os

import redis.asyncio as aioredis
import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from es_client import ElasticsearchClient
from embedder import EmbeddingGenerator
from clusterer import FailureClusterer
from cluster_store import ClusterStore


logger = logging.getLogger(__name__)


ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring",
)


class ClusteringScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.es_client = ElasticsearchClient(ES_URL)
        self.embedder = EmbeddingGenerator(REDIS_URL)
        self.clusterer = FailureClusterer()
        self.store = None
        self.redis = None

    async def start(self):
        await self.embedder.init()
        self.redis = await aioredis.from_url(REDIS_URL)

        pg_url = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
        pg_pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=10)
        self.store = ClusterStore(pg_pool)

        self.scheduler.add_job(self.run_clustering, "interval", minutes=5)
        self.scheduler.start()
        logger.info("Clustering scheduler started")

    async def shutdown(self):
        self.scheduler.shutdown(wait=False)
        if self.redis:
            await self.redis.close()

    async def run_clustering(self):
        try:
            entries = await self.es_client.get_recent_errors(minutes=30)

            if len(entries) < 2:
                logger.info("Insufficient error logs for clustering")
                return

            messages = [e.message for e in entries]
            embeddings = await self.embedder.embed_batch(messages)

            clusters = self.clusterer.cluster(entries, embeddings)

            await self.store.upsert_clusters(clusters, self.embedder)
            await self.store.resolve_stale_clusters()

            summary = [
                {
                    "cluster_id": c.cluster_id,
                    "representative": c.representative_message[:100],
                    "size": c.member_count,
                    "services": c.affected_services,
                }
                for c in clusters
            ]

            await self.redis.publish("cluster_updates", json.dumps(summary))
            logger.info(
                f"Clustered {len(entries)} errors into {len(clusters)} clusters"
            )

        except Exception as exc:
            logger.error(f"Clustering error: {exc}")
