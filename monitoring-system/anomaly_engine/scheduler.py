import asyncio
import json
import logging
import os

import aioredis
import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from models import AnomalyEvent
from prometheus_client import PrometheusClient
from zscore_detector import ZScoreDetector
from isolation_forest_detector import IsolationForestDetector


logger = logging.getLogger(__name__)


SERVICES = ["user-service", "order-service", "payment-service"]

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


class AnomalyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.pg_pool = None
        self.redis = None
        self.prom_client = PrometheusClient(PROMETHEUS_URL)
        self.zscore_detector = ZScoreDetector()
        self.if_detector = IsolationForestDetector()

    async def start(self):
        pg_url = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
        self.pg_pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=10)
        self.redis = await aioredis.from_url(REDIS_URL)

        await self._train_all_models()
        self.scheduler.add_job(self.run_detection, "interval", seconds=60)
        self.scheduler.add_job(self.retrain_models, "interval", hours=24)
        self.scheduler.add_job(self.cleanup_old_anomalies, "interval", hours=1)
        self.scheduler.start()
        logger.info("Scheduler started")

    async def shutdown(self):
        self.scheduler.shutdown(wait=False)
        if self.redis:
            await self.redis.close()
        if self.pg_pool:
            await self.pg_pool.close()

    async def _train_all_models(self):
        tasks = [self.if_detector.train(svc, self.prom_client) for svc in SERVICES]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run_detection(self):
        for service in SERVICES:
            try:
                snapshot = await self.prom_client.get_full_snapshot(service)
                zscore_events = self.zscore_detector.detect_all(snapshot)
                if_event = self.if_detector.detect(snapshot)

                all_events = zscore_events
                if if_event:
                    all_events.append(if_event)

                for event in all_events:
                    dedup_key = f"anomaly_dedup:{event.service}:{event.metric}"
                    if await self.redis.get(dedup_key):
                        continue
                    await self.redis.setex(dedup_key, 600, "1")

                    await self.pg_pool.execute(
                        """
                        INSERT INTO anomalies
                        (service, metric, current_value, mean, std, z_score,
                         anomaly_score, severity, detector, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        event.service,
                        event.metric,
                        event.current_value,
                        event.mean,
                        event.std,
                        event.z_score,
                        event.anomaly_score,
                        event.severity,
                        event.detector,
                        event.timestamp,
                    )

                    await self.redis.publish(
                        "anomaly_events", json.dumps(event.to_dict())
                    )
                    logger.info(f"Published anomaly: {event.service}/{event.metric}")
            except Exception as exc:
                logger.error(f"Detection error for {service}: {exc}")

    async def retrain_models(self):
        await self._train_all_models()

    async def cleanup_old_anomalies(self):
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM anomalies WHERE created_at < NOW() - INTERVAL '7 days'"
            )
