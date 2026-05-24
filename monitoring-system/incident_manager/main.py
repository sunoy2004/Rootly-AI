import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis
import asyncpg

from auth import LoginRequest, create_access_token, USERS, pwd_context
from api import router as api_router
from ws_hub import router as ws_router
from manager import IncidentManager
from lifecycle import IncidentLifecycle


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


pg_pool: Optional[asyncpg.Pool] = None
redis: Optional[aioredis.Redis] = None
manager: Optional[IncidentManager] = None
lifecycle: Optional[IncidentLifecycle] = None


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
                    payload = json.loads(message["data"])
                    await handler_func(payload)
        except Exception as e:
            logger.error(f"Redis disconnected: {e}. Retrying in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pg_pool, redis, manager, lifecycle

    pg_url = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
    pg_pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=10)
    redis = await aioredis.from_url(REDIS_URL)

    manager = IncidentManager(pg_pool, redis)
    lifecycle = IncidentLifecycle(pg_pool, redis)
    await lifecycle.start()

    async with pg_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                incident_id UUID REFERENCES incidents(id),
                root_cause TEXT NOT NULL,
                severity VARCHAR(20) NOT NULL,
                confidence FLOAT NOT NULL,
                affected_services TEXT[] NOT NULL DEFAULT '{}',
                recommended_actions TEXT[] NOT NULL DEFAULT '{}',
                summary TEXT,
                raw_response JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

    task1 = asyncio.create_task(
        subscribe_with_retry(REDIS_URL, "rule_matches", manager.handle_rule_match)
    )
    from ws_hub import redis_event_bridge

    task_bridge = asyncio.create_task(redis_event_bridge(REDIS_URL))

    yield

    task1.cancel()
    task_bridge.cancel()
    await lifecycle.shutdown()
    await redis.close()
    await pg_pool.close()


app = FastAPI(title="Incident Manager", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/auth/login")
async def login(request: LoginRequest):
    if request.username not in USERS:
        pass
    elif not pwd_context.verify(request.password, USERS[request.username]):
        pass
    else:
        token = create_access_token({"sub": request.username})
        return {"access_token": token, "token_type": "bearer"}

    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "incident-manager"}


app.include_router(api_router, dependencies=[])
app.include_router(ws_router, dependencies=[])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8007)
