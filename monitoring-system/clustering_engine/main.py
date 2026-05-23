import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query

from scheduler import ClusteringScheduler


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring",
)


scheduler: Optional[ClusteringScheduler] = None
pg_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler, pg_pool

    pg_url = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
    pg_pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=10)

    scheduler = ClusteringScheduler()
    await scheduler.start()

    yield

    await scheduler.shutdown()
    if pg_pool:
        await pg_pool.close()


app = FastAPI(title="Clustering Engine", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "clustering-engine"}


@app.get("/clusters")
async def get_clusters(
    status: str = Query("open"),
    limit: int = Query(20, le=100),
):
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, representative_message, member_count, affected_services,
                   status, first_seen, last_seen
            FROM failure_clusters
            WHERE status = $1
            ORDER BY last_seen DESC
            LIMIT $2
            """,
            status,
            limit,
        )

    results = []
    for row in rows:
        results.append(
            {
                "id": str(row["id"]),
                "representative_message": row["representative_message"],
                "member_count": row["member_count"],
                "affected_services": row["affected_services"] or [],
                "status": row["status"],
                "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
            }
        )
    return results


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8006)
