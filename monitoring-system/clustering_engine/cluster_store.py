import logging
from typing import List

import asyncpg
import faiss
import numpy as np

from models import FailureCluster
from embedder import EmbeddingGenerator


logger = logging.getLogger(__name__)


class ClusterStore:
    def __init__(self, pg_pool: asyncpg.Pool):
        self.pg_pool = pg_pool

    async def upsert_clusters(
        self, new_clusters: List[FailureCluster], embedder: EmbeddingGenerator
    ):
        if not new_clusters:
            return

        async with self.pg_pool.acquire() as conn:
            existing = await conn.fetch(
                """
                SELECT id, representative_message, member_count, affected_services,
                       first_seen, last_seen
                FROM failure_clusters
                WHERE status = 'open'
                """
            )

        if existing:
            existing_messages = [row["representative_message"] for row in existing]
            existing_embeddings = await embedder.embed_batch(existing_messages)

            dim = existing_embeddings.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(existing_embeddings)

            for new_cluster in new_clusters:
                new_embedding = await embedder.embed_batch(
                    [new_cluster.representative_message]
                )
                new_embedding = new_embedding[0].reshape(1, -1)

                scores, indices = index.search(new_embedding, 1)
                best_score = scores[0][0] if len(scores[0]) > 0 else 0
                best_idx = indices[0][0] if len(indices[0]) > 0 else None

                if best_score > 0.85 and best_idx is not None:
                    existing_row = existing[best_idx]
                    existing_services = existing_row["affected_services"] or []
                    new_services = list(
                        set(existing_services + new_cluster.affected_services)
                    )

                    async with self.pg_pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE failure_clusters
                            SET member_count = member_count + $1,
                                last_seen = $2,
                                affected_services = $3
                            WHERE id = $4
                            """,
                            new_cluster.member_count,
                            new_cluster.last_seen,
                            new_services,
                            existing_row["id"],
                        )
                    logger.info(
                        f"Merged cluster into existing: {existing_row['id']}"
                    )
                else:
                    await self._insert_cluster(new_cluster)
        else:
            for cluster in new_clusters:
                await self._insert_cluster(cluster)

    async def _insert_cluster(self, cluster: FailureCluster):
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO failure_clusters
                (representative_message, member_count, affected_services,
                 first_seen, last_seen, status)
                VALUES ($1, $2, $3, $4, $5, 'open')
                """,
                cluster.representative_message,
                cluster.member_count,
                cluster.affected_services,
                cluster.first_seen,
                cluster.last_seen,
            )
        logger.info(f"Inserted new cluster with {cluster.member_count} members")

    async def resolve_stale_clusters(self):
        async with self.pg_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE failure_clusters
                SET status = 'resolved'
                WHERE status = 'open'
                AND last_seen < NOW() - INTERVAL '30 minutes'
                """
            )
            logger.info(f"Resolved stale clusters: {result}")
