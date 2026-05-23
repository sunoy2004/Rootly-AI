import asyncio
import json
import logging
import os
from dataclasses import asdict

import aioredis

from anomaly_engine.prometheus_client import PrometheusClient
from evaluator import RuleEvaluator


logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

SERVICES = ["user-service", "order-service", "payment-service"]


async def subscribe_with_retry(redis_url: str, channel: str, handler_func):
    backoff = 1
    while True:
        try:
            redis = aioredis.from_url(redis_url)
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)
            backoff = 1
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await handler_func(message["data"])
        except Exception as e:
            logger.error(f"Redis disconnected: {e}. Retrying in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


class RuleEngine:
    def __init__(self):
        self.redis = None
        self.prom_client = PrometheusClient(PROMETHEUS_URL)
        self.evaluator = RuleEvaluator()

    async def start(self):
        self.redis = aioredis.from_url(REDIS_URL)
        await subscribe_with_retry(REDIS_URL, "anomaly_events", self.handle_anomaly)

    async def handle_anomaly(self, data: bytes):
        try:
            event = json.loads(data)
            service = event.get("service", "")
            logger.info(f"Processing anomaly: {service}/{event.get('metric')}")

            import asyncio
            snapshots = {}
            results = await asyncio.gather(
                *[
                    self.prom_client.get_full_snapshot(svc)
                    for svc in SERVICES
                ]
            )
            for svc, snap in zip(SERVICES, results):
                snapshots[svc] = snap

            match = self.evaluator.evaluate(event, snapshots)

            if match:
                payload = {
                    "type": "rule_match",
                    "rule_match": asdict(match),
                    "anomaly_event": event,
                }
                await self.redis.publish("rule_matches", json.dumps(payload))
                logger.info(f"Rule matched: {match.rule_name} for {service}")
            else:
                await self.redis.publish("needs_ai_analysis", json.dumps(event))
                logger.info(f"No rule for {service}, routing to AI")

        except Exception as exc:
            logger.error(f"Error handling anomaly: {exc}")
