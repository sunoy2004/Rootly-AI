import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
import aioredis
import asyncpg

from deduplicator import AlertDeduplicator
from slack_alerter import SlackAlerter
from email_alerter import EmailAlerter


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring",
)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


redis: Optional[aioredis.Redis] = None
pg_pool: Optional[asyncpg.Pool] = None
dedup: Optional[AlertDeduplicator] = None
slack_alerter: Optional[SlackAlerter] = None
email_alerter: Optional[EmailAlerter] = None


async def subscribe_with_retry(redis_url: str, channel: str, handler_func):
    backoff = 1
    while True:
        try:
            redis_client = await aioredis.from_url(redis_url)
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            backoff = 1
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await handler_func(message["data"])
        except Exception as e:
            logger.error(f"Redis disconnected: {e}. Retrying in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


async def handle_alert(data: bytes):
    payload = json.loads(data)
    incident = payload.get("incident", payload)
    is_escalation = payload.get("escalation", False)
    ai_analysis = payload.get("ai_analysis")

    incident_id = incident.get("id", "")

    if not await dedup.should_send(incident_id, is_escalation):
        logger.info(f"Alert deduplicated for incident {incident_id}")
        return

    await slack_alerter.send(incident, ai_analysis, is_escalation)
    await email_alerter.send(incident, ai_analysis)

    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE incidents SET alert_sent = TRUE WHERE id = $1",
            incident_id,
        )

    logger.info(f"Alert sent for incident {incident_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis, pg_pool, dedup, slack_alerter, email_alerter

    redis = await aioredis.from_url(REDIS_URL)

    pg_url = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
    pg_pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=10)

    dedup = AlertDeduplicator(redis)
    slack_alerter = SlackAlerter(SLACK_WEBHOOK_URL)
    email_alerter = EmailAlerter()

    task = asyncio.create_task(
        subscribe_with_retry(REDIS_URL, "incidents_to_alert", handle_alert)
    )

    yield

    task.cancel()
    await slack_alerter.close()
    await redis.close()
    await pg_pool.close()


app = FastAPI(title="Alert System", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "alert-system"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8009)
