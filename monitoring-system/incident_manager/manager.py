import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis
import asyncpg


logger = logging.getLogger(__name__)


def serialize_row(row_dict: dict) -> dict:
    out = {}
    for key, value in row_dict.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, UUID):
            out[key] = str(value)
        else:
            out[key] = value
    return out


class IncidentManager:
    def __init__(self, pg_pool: asyncpg.Pool, redis: aioredis.Redis):
        self.pg_pool = pg_pool
        self.redis = redis

    async def handle_rule_match(self, payload: dict) -> dict:
        rule_match = payload.get("rule_match", {})
        anomaly_event = payload.get("anomaly_event", {})
        service = anomaly_event.get("service", "")
        rule_name = rule_match.get("rule_name", "unknown").replace("_", " ").title()

        title = f"{service}: {rule_name}"
        severity = rule_match.get("severity", "WARNING")
        confidence = rule_match.get("confidence", 0.5)
        diagnosis = rule_match.get("diagnosis", "")

        async with self.pg_pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id, severity FROM incidents
                WHERE $1 = ANY(affected_services)
                AND status IN ('OPEN', 'ACKNOWLEDGED')
                AND created_at > NOW() - INTERVAL '30 minutes'
                """,
                service,
            )

            if existing:
                if severity == "CRITICAL" and existing["severity"] == "WARNING":
                    await conn.execute(
                        "UPDATE incidents SET severity = $1 WHERE id = $2",
                        severity,
                        existing["id"],
                    )
                incident = await conn.fetchrow(
                    "SELECT * FROM incidents WHERE id = $1", existing["id"]
                )
                incident_dict = serialize_row(dict(incident))
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO incidents
                    (title, status, severity, affected_services, root_cause,
                     confidence, source, alert_sent)
                    VALUES ($1, 'OPEN', $2, $3, $4, $5, 'RULE_ENGINE', FALSE)
                    RETURNING *
                    """,
                    title,
                    severity,
                    [service],
                    diagnosis,
                    confidence,
                )
                incident_dict = serialize_row(dict(row))

        await self.redis.publish("incidents_to_alert", json.dumps(incident_dict))
        return incident_dict

    async def handle_needs_ai(self, payload: dict) -> dict:
        anomaly_event = payload.get("anomaly_event", payload)
        service = anomaly_event.get("service", "")
        metric = anomaly_event.get("metric", "")
        title = f"{service}: Anomaly detected - {metric}"
        severity = anomaly_event.get("severity", "WARNING")

        async with self.pg_pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id FROM incidents
                WHERE $1 = ANY(affected_services)
                AND status IN ('OPEN', 'ACKNOWLEDGED')
                AND created_at > NOW() - INTERVAL '30 minutes'
                """,
                service,
            )

            if existing:
                incident = await conn.fetchrow(
                    "SELECT * FROM incidents WHERE id = $1", existing["id"]
                )
                incident_dict = serialize_row(dict(incident))
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO incidents
                    (title, status, severity, affected_services, root_cause,
                     confidence, source, alert_sent)
                    VALUES ($1, 'OPEN', $2, $3, NULL, NULL, 'AI_AGENT', FALSE)
                    RETURNING *
                    """,
                    title,
                    severity,
                    [service],
                )
                incident_dict = serialize_row(dict(row))

        await self.redis.publish(
            "incidents_for_ai",
            json.dumps({"incident": incident_dict, "anomaly_event": anomaly_event}),
        )
        return incident_dict

    async def acknowledge(self, incident_id: str):
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE incidents
                SET status = 'ACKNOWLEDGED', acknowledged_at = NOW()
                WHERE id = $1
                """,
                incident_id,
            )

    async def resolve(self, incident_id: str, resolution_notes: str):
        async with self.pg_pool.acquire() as conn:
            incident = await conn.fetchrow(
                "SELECT * FROM incidents WHERE id = $1", incident_id
            )
            await conn.execute(
                """
                UPDATE incidents
                SET status = 'RESOLVED', resolved_at = NOW(), resolution_notes = $2
                WHERE id = $1
                """,
                incident_id,
                resolution_notes,
            )

        incident_dict = serialize_row(dict(incident))
        incident_dict["status"] = "RESOLVED"
        incident_dict["resolved_at"] = datetime.utcnow().isoformat()
        incident_dict["resolution_notes"] = resolution_notes

        await self.redis.publish("incidents_resolved", json.dumps(incident_dict))
