import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
import aioredis
import asyncpg
import httpx

from agent import RootCauseAgent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring",
)
INCIDENT_MANAGER_URL = os.getenv("INCIDENT_MANAGER_URL", "http://incident-manager:8007")


agent: Optional[RootCauseAgent] = None
redis: Optional[aioredis.Redis] = None
pg_pool: Optional[asyncpg.Pool] = None


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


async def handle_incident_for_ai(data: bytes):
    payload = json.loads(data)
    incident = payload.get("incident", payload)
    anomaly_event = payload.get("anomaly_event", {})

    try:
        result = await agent.analyze(incident, anomaly_event)

        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE incidents
                SET root_cause = $1, confidence = $2
                WHERE id = $3
                """,
                result.get("probable_cause", ""),
                result.get("confidence", 0.0),
                incident["id"],
            )

        enriched = {
            **incident,
            "root_cause": result.get("probable_cause"),
            "confidence": result.get("confidence"),
            "ai_analysis": result,
        }
        await redis.publish("incidents_to_alert", json.dumps(enriched))

        logger.info(
            f"AI analyzed {incident['id']}: "
            f"{result.get('probable_cause', '')[:80]}"
        )
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        incident["root_cause"] = "AI analysis failed"
        await redis.publish("incidents_to_alert", json.dumps(incident))


async def handle_resolved(data: bytes):
    incident = json.loads(data)
    agent.memory.store(incident)
    logger.info(f"Stored incident {incident['id']} in memory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, redis, pg_pool

    agent = RootCauseAgent()
    redis = await aioredis.from_url(REDIS_URL)

    pg_url = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
    pg_pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=10)

    task1 = asyncio.create_task(
        subscribe_with_retry(REDIS_URL, "incidents_for_ai", handle_incident_for_ai)
    )
    task2 = asyncio.create_task(
        subscribe_with_retry(REDIS_URL, "incidents_resolved", handle_resolved)
    )

    yield

    task1.cancel()
    task2.cancel()
    await redis.close()
    await pg_pool.close()


app = FastAPI(title="AI Agent", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ai-agent",
        "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o"),
        "rate_limit": "5/minute",
    }


@app.get("/analyze/{incident_id}")
async def analyze_incident(incident_id: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{INCIDENT_MANAGER_URL}/incidents/{incident_id}"
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail="Incident not found")
            data = resp.json()
            incident = data.get("incident", data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async with pg_pool.acquire() as conn:
        anomaly = await conn.fetchrow(
            """
            SELECT * FROM anomalies
            WHERE service = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            incident.get("affected_services", [""])[0],
        )

    anomaly_event = dict(anomaly) if anomaly else {}

    result = await agent.analyze(incident, anomaly_event)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8008)
