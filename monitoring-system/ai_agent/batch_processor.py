import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
import redis.asyncio as aioredis

from agent import RootCauseAgent
from context_builder import IncidentContextBuilder


logger = logging.getLogger(__name__)

BATCH_INTERVAL_SEC = int(__import__("os").getenv("AI_BATCH_INTERVAL_SEC", "30"))
COOLDOWN_TTL_SEC = int(__import__("os").getenv("AI_COOLDOWN_TTL_SEC", "600"))
MIN_SEVERITY = {"WARNING", "CRITICAL"}


def _serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    return obj


def _cluster_key(event: dict) -> str:
    service = event.get("service", "unknown")
    metric = event.get("metric", "unknown")
    return f"{service}:{metric}"


class AIBatchProcessor:
    """Batch unknown anomalies for 30s, one Groq call per cluster."""

    def __init__(
        self,
        agent: RootCauseAgent,
        redis: aioredis.Redis,
        pg_pool: asyncpg.Pool,
    ):
        self.agent = agent
        self.redis = redis
        self.pg_pool = pg_pool
        self.context_builder = IncidentContextBuilder()
        self._queue: List[dict] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, event: dict):
        severity = event.get("severity", "WARNING")
        if severity not in MIN_SEVERITY:
            return
        async with self._lock:
            self._queue.append(event)
        logger.info(
            f"Queued for AI batch: {event.get('service')}/{event.get('metric')} "
            f"severity={severity} (queue={len(self._queue)})"
        )

    async def run_forever(self):
        logger.info(f"AI batch processor started (interval={BATCH_INTERVAL_SEC}s)")
        while True:
            await asyncio.sleep(BATCH_INTERVAL_SEC)
            await self.flush()

    async def flush(self):
        async with self._lock:
            if not self._queue:
                return
            batch = self._queue[:]
            self._queue.clear()

        clusters: Dict[str, List[dict]] = defaultdict(list)
        for event in batch:
            clusters[_cluster_key(event)].append(event)

        logger.info(f"AI batch flush: {len(batch)} events -> {len(clusters)} clusters")

        for key, events in clusters.items():
            try:
                await self._process_cluster(key, events)
            except Exception as exc:
                logger.error(f"Cluster processing failed for {key}: {exc}", exc_info=True)

    async def _process_cluster(self, cluster_key: str, events: List[dict]):
        cluster_hash = hashlib.sha256(cluster_key.encode()).hexdigest()[:16]
        dedup_key = f"ai_analysis:{cluster_hash}"

        if await self.redis.get(dedup_key):
            logger.info(f"Skipping cluster {cluster_key} (cooldown active)")
            return

        representative = max(events, key=lambda e: e.get("severity") == "CRITICAL")
        service = representative.get("service", "unknown")
        metric = representative.get("metric", "unknown")
        severity = representative.get("severity", "WARNING")

        incident_stub = {
            "title": f"{service}: Clustered anomaly - {metric} ({len(events)} events)",
            "severity": severity,
            "affected_services": list({e.get("service", service) for e in events}),
            "source": "AI_AGENT",
        }

        summary_context = await self._build_batch_summary(events)

        try:
            result = await self.agent.analyze_batch(incident_stub, representative, summary_context)
        except Exception as exc:
            logger.error(f"Groq batch analysis failed: {exc}")
            return

        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO incidents
                (title, status, severity, affected_services, root_cause,
                 confidence, source, alert_sent)
                VALUES ($1, 'OPEN', $2, $3, $4, $5, 'AI_AGENT', FALSE)
                RETURNING *
                """,
                incident_stub["title"],
                result.get("severity", severity),
                incident_stub["affected_services"],
                result.get("root_cause", ""),
                float(result.get("confidence", 0.5)),
            )
            incident_id = str(row["id"])

            await conn.execute(
                """
                INSERT INTO ai_analyses
                (incident_id, root_cause, severity, confidence, affected_services,
                 recommended_actions, summary, raw_response)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                incident_id,
                result.get("root_cause", ""),
                result.get("severity", severity),
                float(result.get("confidence", 0.0)),
                incident_stub["affected_services"],
                result.get("recommended_actions", []),
                result.get("summary", ""),
                json.dumps(result),
            )

            cluster_row = await conn.fetchrow(
                """
                SELECT id FROM failure_clusters
                WHERE status = 'open' AND $1 = ANY(affected_services)
                ORDER BY last_seen DESC LIMIT 1
                """,
                service,
            )
            if cluster_row:
                await conn.execute(
                    "UPDATE incidents SET cluster_id = $1 WHERE id = $2",
                    cluster_row["id"],
                    row["id"],
                )

        incident_dict = {k: _serialize(v) for k, v in dict(row).items()}
        incident_dict["ai_analysis"] = result
        incident_dict["cluster_size"] = len(events)

        await self.redis.setex(dedup_key, COOLDOWN_TTL_SEC, "1")
        payload = json.dumps(incident_dict)
        await self.redis.publish("ai_analysis_completed", payload)
        await self.redis.publish("incidents_to_alert", payload)

        logger.info(
            f"AI cluster incident created: {incident_id} "
            f"root_cause={result.get('root_cause', '')[:60]} "
            f"events={len(events)}"
        )

    async def _build_batch_summary(self, events: List[dict]) -> Dict[str, Any]:
        services = list({e.get("service") for e in events if e.get("service")})
        metrics = [e.get("metric") for e in events]
        max_z = max((e.get("z_score") or 0 for e in events), default=0)

        return {
            "cluster_size": len(events),
            "services": services,
            "metrics": metrics,
            "max_z_score": max_z,
            "timeline": [
                {
                    "service": e.get("service"),
                    "metric": e.get("metric"),
                    "severity": e.get("severity"),
                    "value": e.get("current_value"),
                }
                for e in events[:20]
            ],
        }
