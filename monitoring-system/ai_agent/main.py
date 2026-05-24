import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis
import asyncpg
import httpx

from agent import RootCauseAgent
from batch_processor import AIBatchProcessor


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring",
)
INCIDENT_MANAGER_URL = os.getenv("INCIDENT_MANAGER_URL", "http://incident-manager:8007")


agent = None
redis = None
pg_pool = None
batch_processor = None


async def subscribe_with_retry(redis_url: str, channel: str, handler_func):
    backoff = 1
    while True:
        try:
            redis_client = await aioredis.from_url(redis_url)
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            backoff = 1
            logger.info(f"Subscribed to Redis channel: {channel}")
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await handler_func(message["data"])
        except Exception as e:
            logger.error(f"Redis disconnected on {channel}: {e}. Retrying in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


async def handle_needs_ai_analysis(data: bytes):
    """Queue unknown anomalies — batched Groq call every 30s, not per-event."""
    try:
        event = json.loads(data)
        await batch_processor.enqueue(event)
    except Exception as exc:
        logger.error(f"Failed to queue anomaly for AI batch: {exc}")


async def handle_resolved(data: bytes):
    incident = json.loads(data)
    agent.memory.store(incident)
    logger.info(f"Stored incident {incident.get('id')} in ChromaDB memory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, redis, pg_pool, batch_processor

    agent = RootCauseAgent()
    redis = await aioredis.from_url(REDIS_URL)

    pg_url = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
    pg_pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=10)

    batch_processor = AIBatchProcessor(agent, redis, pg_pool)

    task_batch = asyncio.create_task(batch_processor.run_forever())
    task_sub = asyncio.create_task(
        subscribe_with_retry(REDIS_URL, "needs_ai_analysis", handle_needs_ai_analysis)
    )
    task_resolved = asyncio.create_task(
        subscribe_with_retry(REDIS_URL, "incidents_resolved", handle_resolved)
    )

    yield

    task_batch.cancel()
    task_sub.cancel()
    task_resolved.cancel()
    await redis.aclose()
    await pg_pool.close()


app = FastAPI(title="AI Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ai-agent",
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        "llm_model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "batch_interval_sec": int(os.getenv("AI_BATCH_INTERVAL_SEC", "30")),
        "rate_limit": "5/minute",
    }


@app.get("/analyze/{incident_id}")
async def analyze_incident(incident_id: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{INCIDENT_MANAGER_URL}/incidents/{incident_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Incident not found")
        data = resp.json()
        incident = data.get("incident", data)

    service = incident.get("affected_services", [""])[0]
    async with pg_pool.acquire() as conn:
        anomaly = await conn.fetchrow(
            """
            SELECT * FROM anomalies WHERE service = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            service,
        )

    return await agent.analyze(incident, dict(anomaly) if anomaly else {})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8008)
