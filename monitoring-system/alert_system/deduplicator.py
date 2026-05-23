import aioredis


class AlertDeduplicator:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def should_send(
        self, incident_id: str, is_escalation: bool = False
    ) -> bool:
        if is_escalation:
            return True

        key = f"alert_sent:{incident_id}"
        exists = await self.redis.get(key)

        if exists:
            return False

        await self.redis.setex(key, 3600, "1")
        return True
