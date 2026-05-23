import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from scheduler import AnomalyScheduler, SERVICES


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


scheduler: Optional[AnomalyScheduler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    scheduler = AnomalyScheduler()
    await scheduler.start()
    yield
    await scheduler.shutdown()


app = FastAPI(title="Anomaly Engine", lifespan=lifespan)


class AnomalyResponse(BaseModel):
    id: str
    service: str
    metric: str
    current_value: float
    mean: float
    std: float
    z_score: Optional[float]
    anomaly_score: Optional[float]
    severity: str
    detector: str
    timestamp: datetime
    created_at: datetime


@app.get("/health")
async def health():
    models_trained = {}
    if scheduler and scheduler.if_detector:
        for service in SERVICES:
            models_trained[service] = scheduler.if_detector.is_trained.get(
                service, False
            )
    return {
        "status": "ok",
        "service": "anomaly-engine",
        "models_trained": models_trained,
    }


@app.get("/anomalies")
async def get_anomalies(
    service: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    if not scheduler or not scheduler.pg_pool:
        return []

    conditions = ["1=1"]
    params = []
    if service:
        conditions.append("service = $1")
        params.append(service)
    if severity:
        conditions.append("severity = $2" if params else "severity = $1")
        params.append(severity)

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT id, service, metric, current_value, mean, std, z_score,
               anomaly_score, severity, detector, timestamp, created_at
        FROM anomalies
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ${len(params) + 1}
    """
    params.append(limit)

    rows = await scheduler.pg_pool.fetch(query, *params)

    results = []
    for row in rows:
        results.append(
            {
                "id": str(row["id"]),
                "service": row["service"],
                "metric": row["metric"],
                "current_value": row["current_value"],
                "mean": float(row["mean"]) if row["mean"] else 0.0,
                "std": float(row["std"]) if row["std"] else 0.0,
                "z_score": float(row["z_score"]) if row["z_score"] else None,
                "anomaly_score": float(row["anomaly_score"])
                if row["anomaly_score"]
                else None,
                "severity": row["severity"],
                "detector": row["detector"],
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )
    return results


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
