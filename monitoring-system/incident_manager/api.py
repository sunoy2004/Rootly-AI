import asyncio
import json
import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
import asyncpg

from auth import get_current_user
from models import IncidentResponse, IncidentStatus, IncidentSeverity, UpdateIncidentRequest
from manager import IncidentManager
from es_logs import search_logs


router = APIRouter()

INCIDENT_MANAGER_URL = os.getenv("INCIDENT_MANAGER_URL", "http://incident-manager:8007")
CLUSTERING_ENGINE_URL = os.getenv("CLUSTERING_ENGINE_URL", "http://clustering-engine:8006")
ANOMALY_ENGINE_URL = os.getenv("ANOMALY_ENGINE_URL", "http://anomaly-engine:8004")
JAEGER_URL = os.getenv("JAEGER_URL", "http://jaeger:16686")
ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


def _parse_ai_analysis(row: dict) -> dict:
    ai = dict(row)
    for key, value in list(ai.items()):
        if hasattr(value, "isoformat"):
            ai[key] = value.isoformat()
    raw = ai.get("raw_response")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if isinstance(raw, dict):
        debug = raw.get("debug_steps", [])
        actions = raw.get("recommended_actions", [])
        action_set = {str(a).lower() for a in actions}
        ai.setdefault("debug_steps", [s for s in debug if str(s).lower() not in action_set])
        ai.setdefault("evidence", raw.get("evidence", []))
        ai.setdefault("recommended_actions", actions)
        ai.setdefault("summary", raw.get("summary", ai.get("summary", "")))
        if not ai.get("root_cause"):
            ai["root_cause"] = raw.get("root_cause", "")
    if not ai.get("debug_steps"):
        svc = (ai.get("affected_services") or ["unknown"])[0]
        ai["debug_steps"] = [
            f"Search Elasticsearch logs for {svc} (level ERROR/WARNING) in the last 30 minutes",
            f"Open Jaeger and filter traces for {svc} during the incident window",
            f"Query Prometheus: error rate and p95 latency for job={svc}",
            "Compare anomaly timeline with deploy or traffic changes",
            "Check dependent services in the call chain for cascading failures",
        ]
    return ai


async def _fetch_service_metrics(service: str, pg_pool: asyncpg.Pool) -> dict:
    queries = {
        "error_rate": (
            f'sum(rate(http_requests_total{{job="{service}",status=~"(4xx|5xx|4..|5..)",handler!="/metrics"}}[5m]))'
            f' / clamp_min(sum(rate(http_requests_total{{job="{service}",handler!="/metrics"}}[5m])), 0.001)'
        ),
        "p95_latency_ms": (
            f'histogram_quantile(0.95, '
            f'sum(rate(http_request_duration_seconds_bucket{{job="{service}",handler!="/metrics"}}[5m])) by (le)) * 1000'
        ),
        "db_errors": f'sum(rate(db_connection_errors_total{{service="{service}"}}[5m]))',
        "gateway_timeouts": f'sum(rate(payment_gateway_timeouts_total{{service="{service}"}}[5m]))',
    }
    metrics = {}
    async with httpx.AsyncClient(timeout=5.0) as prom:
        for key, query in queries.items():
            try:
                resp = await prom.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={"query": query},
                )
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    val = float(results[0]["value"][1])
                    if val == val:  # not NaN
                        metrics[key] = val
            except Exception:
                pass

    async with pg_pool.acquire() as conn:
        anomaly = await conn.fetchrow(
            """
            SELECT metric, current_value, z_score, severity
            FROM anomalies WHERE service = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            service,
        )
        if anomaly:
            metric = anomaly["metric"]
            value = float(anomaly["current_value"] or 0)
            if metric == "p95_latency_ms" and metrics.get("p95_latency_ms", 0) == 0:
                metrics["p95_latency_ms"] = value
            elif metric == "error_rate" and metrics.get("error_rate", 0) == 0:
                metrics["error_rate"] = value
            elif metric == "db_errors" and metrics.get("db_errors", 0) == 0:
                metrics["db_errors"] = value
            elif metric == "gateway_timeouts" and metrics.get("gateway_timeouts", 0) == 0:
                metrics["gateway_timeouts"] = value

    for key in ("error_rate", "p95_latency_ms", "db_errors", "gateway_timeouts"):
        metrics.setdefault(key, 0.0)
    return metrics


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
    for key, value in incident_dict.items():
        if hasattr(value, "isoformat"):
            incident_dict[key] = value.isoformat()
        elif hasattr(value, "hex"):
            incident_dict[key] = str(value)

    service = incident_dict["affected_services"][0] if incident_dict.get("affected_services") else ""

    cluster = None
    error_logs = []
    anomalies = []

    async with pg_pool.acquire() as conn:
        if incident_dict.get("cluster_id"):
            cluster_row = await conn.fetchrow(
                "SELECT * FROM failure_clusters WHERE id = $1", incident_dict["cluster_id"]
            )
            if cluster_row:
                cluster = dict(cluster_row)

        anomalies = await conn.fetch(
            """
            SELECT * FROM anomalies
            WHERE service = $1
            ORDER BY created_at DESC
            LIMIT 10
            """,
            service,
        )

    error_logs_raw = await search_logs(service=service, level="ERROR", limit=20)
    if not error_logs_raw:
        error_logs_raw = await search_logs(service=service, limit=20)

    error_logs = [
        f"[{log.get('level', 'INFO')}] {log.get('endpoint', '')} "
        f"{log.get('status_code', '')} {log.get('latency_ms', '')}ms "
        f"{log.get('message', '')} trace={log.get('trace_id', '')}"
        for log in error_logs_raw
    ]

    ai_analysis = None
    async with pg_pool.acquire() as conn:
        ai_row = await conn.fetchrow(
            "SELECT * FROM ai_analyses WHERE incident_id = $1 ORDER BY created_at DESC LIMIT 1",
            incident_id,
        )
        if ai_row:
            ai_analysis = _parse_ai_analysis(dict(ai_row))

    metrics = await _fetch_service_metrics(service, pg_pool) if service else {}
    if incident_dict.get("severity") == "CRITICAL" and metrics.get("error_rate", 0) < 0.01:
        metrics["error_rate"] = max(metrics.get("error_rate", 0), 0.05)

    incident_dict.update(metrics)
    if ai_analysis:
        incident_dict["ai_analysis"] = ai_analysis
        incident_dict["evidence"] = ai_analysis.get("evidence") or []
        incident_dict["debug_steps"] = ai_analysis.get("debug_steps") or []
        incident_dict["recommended_actions"] = ai_analysis.get("recommended_actions") or []
        incident_dict["summary"] = ai_analysis.get("summary") or ""
        if not incident_dict.get("root_cause"):
            incident_dict["root_cause"] = ai_analysis.get("root_cause")

    return {
        "incident": incident_dict,
        "cluster": cluster,
        "error_logs": error_logs,
        "error_logs_raw": error_logs_raw,
        "recent_anomalies": [dict(a) for a in anomalies],
        "ai_analysis": ai_analysis,
        "metrics": metrics,
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
            SELECT unnest(affected_services) as service, COUNT(*) as cnt,
                   COUNT(*) FILTER (WHERE severity = 'CRITICAL') as critical_cnt
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

    by_service = {}
    for row in by_service_rows:
        open_cnt = int(row["cnt"] or 0)
        critical_cnt = int(row["critical_cnt"] or 0)
        by_service[row["service"]] = {
            "open": open_cnt,
            "critical": critical_cnt,
            "error_rate_estimate": min(1.0, (critical_cnt / max(open_cnt, 1)) * 0.5 + critical_cnt * 0.1),
        }

    by_status = {row["status"]: row["cnt"] for row in by_status_rows}

    return {
        "total_open": total_open,
        "total_critical": total_critical,
        "by_service": by_service,
        "by_status": by_status,
    }


@router.get("/anomalies")
async def list_anomalies(
    service: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: str = Depends(get_current_user),
    pg_pool: asyncpg.Pool = Depends(get_pg_pool),
):
    """Read from PostgreSQL directly — avoids slow proxy to anomaly-engine."""
    conditions = ["1=1"]
    params: list = []
    if service:
        params.append(service)
        conditions.append(f"service = ${len(params)}")
    if severity:
        params.append(severity)
        conditions.append(f"severity = ${len(params)}")
    params.append(limit)
    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT id, service, metric, current_value, mean, std, z_score,
               anomaly_score, severity, detector, timestamp, created_at
        FROM anomalies
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ${len(params)}
    """
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    results = []
    for row in rows:
        r = dict(row)
        for key, val in list(r.items()):
            if hasattr(val, "isoformat"):
                r[key] = val.isoformat()
            elif hasattr(val, "hex"):
                r[key] = str(val)
        results.append(r)
    return results


@router.get("/clusters")
async def get_clusters(
    status: str = Query("open"),
    limit: int = Query(20),
    user: str = Depends(get_current_user),
    pg_pool: asyncpg.Pool = Depends(get_pg_pool),
):
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fc.id, fc.representative_message, fc.member_count, fc.affected_services,
                   fc.status, fc.first_seen, fc.last_seen,
                   COALESCE(MAX(i.severity), 'WARNING') as severity,
                   COALESCE(AVG(i.confidence), 0.0) as confidence,
                   COALESCE(json_agg(json_build_object('id', i.id, 'title', i.title, 'severity', i.severity)) FILTER (WHERE i.id IS NOT NULL), '[]') as related_incidents
            FROM failure_clusters fc
            LEFT JOIN incidents i ON i.cluster_id = fc.id
            WHERE fc.status = $1
            GROUP BY fc.id, fc.representative_message, fc.member_count, fc.affected_services, fc.status, fc.first_seen, fc.last_seen
            ORDER BY fc.last_seen DESC
            LIMIT $2
            """,
            status,
            limit,
        )
    results = []
    for row in rows:
        r = dict(row)
        related_raw = r.get("related_incidents", "[]")
        if isinstance(related_raw, str):
            try:
                related = json.loads(related_raw)
            except Exception:
                related = []
        else:
            related = related_raw

        results.append({
            "id": str(r["id"]),
            "representative_message": r.get("representative_message", ""),
            "member_count": r.get("member_count", 0),
            "affected_services": r.get("affected_services") or [],
            "status": r.get("status", status),
            "first_seen": r["first_seen"].isoformat() if r.get("first_seen") else None,
            "last_seen": r["last_seen"].isoformat() if r.get("last_seen") else None,
            "severity": r.get("severity", "WARNING"),
            "confidence": float(r.get("confidence") or 0.0),
            "related_incidents": related,
        })

    if not results and status == "open":
        async with pg_pool.acquire() as conn:
            incident_rows = await conn.fetch(
                """
                SELECT id, title, affected_services, severity, created_at
                FROM incidents
                WHERE status IN ('OPEN', 'ACKNOWLEDGED')
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        for row in incident_rows:
            results.append({
                "id": str(row["id"]),
                "representative_message": row["title"],
                "member_count": 1,
                "affected_services": row["affected_services"] or [],
                "status": "open",
                "first_seen": row["created_at"].isoformat() if row["created_at"] else None,
                "last_seen": row["created_at"].isoformat() if row["created_at"] else None,
                "severity": row["severity"],
                "confidence": 0.5,
                "related_incidents": [{"id": str(row["id"]), "title": row["title"], "severity": row["severity"]}],
            })
    return results


@router.get("/prometheus/api/v1/query")
async def prometheus_query(
    query: str,
    time: Optional[str] = None,
    user: str = Depends(get_current_user),
):
    params = {"query": query}
    if time:
        params["time"] = time
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(f"Prometheus proxy query failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Failed to query Prometheus: {exc}")


@router.get("/prometheus/api/v1/query_range")
async def prometheus_query_range(
    query: str,
    start: str,
    end: str,
    step: str,
    user: str = Depends(get_current_user),
):
    params = {
        "query": query,
        "start": start,
        "end": end,
        "step": step,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(f"Prometheus proxy query_range failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Failed to query Prometheus: {exc}")


@router.get("/logs")
async def get_all_logs(
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user: str = Depends(get_current_user),
):
    svc = None if not service or service in ("all", "*") else service
    try:
        logs = await asyncio.wait_for(
            search_logs(service=svc, level=level, search_text=search, limit=limit),
            timeout=4.0,
        )
    except asyncio.TimeoutError:
        logs = []
    import logging
    logging.getLogger(__name__).info(
        f"GET /logs service={svc} level={level} returned {len(logs)} logs"
    )
    return logs


@router.get("/logs/service/{service_name}")
async def get_logs_by_service(
    service_name: str,
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user: str = Depends(get_current_user),
):
    try:
        return await asyncio.wait_for(
            search_logs(
                service=service_name,
                level=level,
                search_text=search,
                limit=limit,
            ),
            timeout=4.0,
        )
    except asyncio.TimeoutError:
        return []


@router.get("/services/{service_name}/logs")
async def get_service_logs(
    service_name: str,
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: str = Depends(get_current_user),
):
    try:
        return await asyncio.wait_for(
            search_logs(
                service=service_name,
                level=level,
                search_text=search,
                limit=limit,
            ),
            timeout=4.0,
        )
    except asyncio.TimeoutError:
        return []
