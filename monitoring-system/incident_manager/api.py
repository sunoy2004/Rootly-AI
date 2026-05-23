import json
import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
import asyncpg

from auth import get_current_user
from models import IncidentResponse, IncidentStatus, IncidentSeverity, UpdateIncidentRequest
from manager import IncidentManager


router = APIRouter()

INCIDENT_MANAGER_URL = os.getenv("INCIDENT_MANAGER_URL", "http://incident-manager:8007")
CLUSTERING_ENGINE_URL = os.getenv("CLUSTERING_ENGINE_URL", "http://clustering-engine:8006")
JAEGER_URL = os.getenv("JAEGER_URL", "http://jaeger:16686")
ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")


def get_manager() -> IncidentManager:
    from main import manager
    return manager


def get_pg_pool() -> asyncpg.Pool:
    from main import pg_pool
    return pg_pool


@router.get("/incidents", response_model=List[IncidentResponse])
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: str = Depends(get_current_user),
    pg_pool: asyncpg.Pool = Depends(get_pg_pool),
):
    conditions = ["1=1"]
    params = []
    if status:
        conditions.append("status = $1")
        params.append(status)
    if severity:
        conditions.append("severity = $2" if len(params) >= 1 else "severity = $1")
        params.append(severity)
    if service:
        conditions.append("$3 = ANY(affected_services)" if len(params) >= 2 else
                          "$2 = ANY(affected_services)" if len(params) >= 1 else
                          "$1 = ANY(affected_services)")
        params.append(service)

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT id, title, status, severity, affected_services, root_cause,
               confidence, source, alert_sent, created_at, acknowledged_at, resolved_at
        FROM incidents
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
    """
    params.extend([limit, offset])

    rows = await pg_pool.fetch(query, *params)

    results = []
    for row in rows:
        results.append(
            IncidentResponse(
                id=str(row["id"]),
                title=row["title"],
                status=row["status"],
                severity=row["severity"],
                affected_services=row["affected_services"] or [],
                root_cause=row["root_cause"],
                confidence=float(row["confidence"]) if row["confidence"] else None,
                source=row["source"],
                alert_sent=row["alert_sent"],
                created_at=row["created_at"],
                acknowledged_at=row["acknowledged_at"],
                resolved_at=row["resolved_at"],
            )
        )
    return results


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    user: str = Depends(get_current_user),
    pg_pool: asyncpg.Pool = Depends(get_pg_pool),
):
    async with pg_pool.acquire() as conn:
        incident = await conn.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", incident_id
        )

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident_dict = dict(incident)

    cluster = None
    if incident_dict.get("cluster_id"):
        cluster = await conn.fetchrow(
            "SELECT * FROM failure_clusters WHERE id = $1", incident_dict["cluster_id"]
        )

    service = incident_dict["affected_services"][0] if incident_dict.get("affected_services") else ""

    error_logs = []
    async with httpx.AsyncClient() as client:
        try:
            es_resp = await client.get(
                f"{ES_URL}/api-logs-*/_search",
                params={
                    "q": f"service:{service} AND level:ERROR",
                    "size": 20,
                    "sort": "@timestamp:desc",
                },
            )
            es_data = es_resp.json()
            for hit in es_data.get("hits", {}).get("hits", []):
                src = hit.get("_source", {})
                error_logs.append(src.get("message", ""))
        except Exception:
            pass

    async with pg_pool.acquire() as conn:
        anomalies = await conn.fetch(
            """
            SELECT * FROM anomalies
            WHERE service = $1
            ORDER BY created_at DESC
            LIMIT 10
            """,
            service,
        )

    return {
        "incident": incident_dict,
        "cluster": dict(cluster) if cluster else None,
        "error_logs": error_logs[:20],
        "recent_anomalies": [dict(a) for a in anomalies],
    }


@router.patch("/incidents/{incident_id}")
async def update_incident(
    incident_id: str,
    request: UpdateIncidentRequest,
    user: str = Depends(get_current_user),
    manager: IncidentManager = Depends(get_manager),
    pg_pool: asyncpg.Pool = Depends(get_pg_pool),
):
    async with pg_pool.acquire() as conn:
        incident = await conn.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", incident_id
        )

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if request.status == IncidentStatus.ACKNOWLEDGED:
        await manager.acknowledge(incident_id)
    elif request.status == IncidentStatus.RESOLVED:
        await manager.resolve(incident_id, request.resolution_notes or "")

    async with pg_pool.acquire() as conn:
        updated = await conn.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", incident_id
        )

    return IncidentResponse(
        id=str(updated["id"]),
        title=updated["title"],
        status=updated["status"],
        severity=updated["severity"],
        affected_services=updated["affected_services"] or [],
        root_cause=updated["root_cause"],
        confidence=float(updated["confidence"]) if updated["confidence"] else None,
        source=updated["source"],
        alert_sent=updated["alert_sent"],
        created_at=updated["created_at"],
        acknowledged_at=updated["acknowledged_at"],
        resolved_at=updated["resolved_at"],
    )


@router.get("/incidents/stats/summary")
async def get_stats(
    user: str = Depends(get_current_user),
    pg_pool: asyncpg.Pool = Depends(get_pg_pool),
):
    async with pg_pool.acquire() as conn:
        total_open = await conn.fetchval(
            "SELECT COUNT(*) FROM incidents WHERE status IN ('OPEN', 'ACKNOWLEDGED')"
        )
        total_critical = await conn.fetchval(
            "SELECT COUNT(*) FROM incidents WHERE severity = 'CRITICAL' AND status IN ('OPEN', 'ACKNOWLEDGED')"
        )

        by_service_rows = await conn.fetch(
            """
            SELECT unnest(affected_services) as service, COUNT(*) as cnt
            FROM incidents
            WHERE status IN ('OPEN', 'ACKNOWLEDGED')
            GROUP BY service
            """
        )

        by_status_rows = await conn.fetch(
            """
            SELECT status, COUNT(*) as cnt
            FROM incidents
            GROUP BY status
            """
        )

    by_service = {row["service"]: row["cnt"] for row in by_service_rows}
    by_status = {row["status"]: row["cnt"] for row in by_status_rows}

    return {
        "total_open": total_open,
        "total_critical": total_critical,
        "by_service": by_service,
        "by_status": by_status,
    }


@router.get("/clusters")
async def get_clusters(
    status: str = Query("open"),
    limit: int = Query(20),
    user: str = Depends(get_current_user),
):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CLUSTERING_ENGINE_URL}/clusters",
            params={"status": status, "limit": limit},
        )
        return resp.json()
