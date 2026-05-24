import json
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncpg
import redis.asyncio as aioredis


logger = logging.getLogger(__name__)


class IncidentLifecycle:
    def __init__(self, pg_pool: asyncpg.Pool, redis: aioredis.Redis):
        self.pg_pool = pg_pool
        self.redis = redis
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        self.scheduler.add_job(self.check_escalations, "interval", minutes=5)
        self.scheduler.start()
        logger.info("Lifecycle scheduler started")

    async def shutdown(self):
        self.scheduler.shutdown(wait=False)

    async def check_escalations(self):
        async with self.pg_pool.acquire() as conn:
            incidents = await conn.fetch(
                """
                SELECT i.*, fc.member_count as current_count
                FROM incidents i
                LEFT JOIN failure_clusters fc ON i.cluster_id = fc.id
                WHERE i.status = 'OPEN'
                AND i.created_at < NOW() - INTERVAL '15 minutes'
                """
            )

        for incident in incidents:
            incident_dict = dict(incident)
            current_count = incident_dict.get("current_count") or 0

            original_member_count = incident_dict.get("member_count", 0)

            if incident_dict["severity"] == "WARNING":
                if original_member_count > 0 and current_count > original_member_count * 1.5:
                    async with self.pg_pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE incidents SET severity = 'CRITICAL' WHERE id = $1",
                            incident_dict["id"],
                        )

                    payload = {"escalation": True, "incident": incident_dict}
                    await self.redis.publish("incidents_to_alert", json.dumps(payload))
                    logger.info(f"Escalated incident {incident_dict['id']}")
