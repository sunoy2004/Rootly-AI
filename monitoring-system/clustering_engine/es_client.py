from datetime import datetime, timedelta
from typing import List

from elasticsearch import AsyncElasticsearch

from models import LogEntry


class ElasticsearchClient:
    def __init__(self, host: str):
        self.es = AsyncElasticsearch([host])

    async def get_recent_errors(self, minutes: int = 30) -> List[LogEntry]:
        query = {
            "bool": {
                "must": [
                    {"term": {"level": "ERROR"}},
                    {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}},
                ]
            }
        }

        result = await self.es.search(
            index="api-logs-*",
            query=query,
            size=500,
            sort=[{"@timestamp": {"order": "desc"}}],
        )

        entries = []
        hits = result.get("hits", {}).get("hits", [])
        for hit in hits:
            src = hit.get("_source", {})
            entries.append(
                LogEntry(
                    id=hit.get("_id", ""),
                    service=src.get("service", ""),
                    level=src.get("level", "ERROR"),
                    message=src.get("message", ""),
                    timestamp=datetime.fromisoformat(
                        src.get("@timestamp", datetime.utcnow().isoformat())
                        if src.get("@timestamp")
                        else datetime.utcnow().isoformat()
                    ),
                    trace_id=src.get("trace_id", ""),
                    status_code=int(src.get("status_code", 0)),
                    latency_ms=float(src.get("latency_ms", 0.0)),
                    endpoint=src.get("endpoint", ""),
                )
            )
        return entries

    async def get_errors_by_service(
        self, service: str, minutes: int = 30
    ) -> List[LogEntry]:
        query = {
            "bool": {
                "must": [
                    {"term": {"level": "ERROR"}},
                    {"term": {"service": service}},
                    {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}},
                ]
            }
        }

        result = await self.es.search(
            index="api-logs-*",
            query=query,
            size=500,
            sort=[{"@timestamp": {"order": "desc"}}],
        )

        entries = []
        hits = result.get("hits", {}).get("hits", [])
        for hit in hits:
            src = hit.get("_source", {})
            entries.append(
                LogEntry(
                    id=hit.get("_id", ""),
                    service=src.get("service", ""),
                    level=src.get("level", "ERROR"),
                    message=src.get("message", ""),
                    timestamp=datetime.fromisoformat(
                        src.get("@timestamp", datetime.utcnow().isoformat())
                        if src.get("@timestamp")
                        else datetime.utcnow().isoformat()
                    ),
                    trace_id=src.get("trace_id", ""),
                    status_code=int(src.get("status_code", 0)),
                    latency_ms=float(src.get("latency_ms", 0.0)),
                    endpoint=src.get("endpoint", ""),
                )
            )
        return entries

    async def get_logs_by_trace_id(self, trace_id: str) -> List[LogEntry]:
        query = {"term": {"trace_id": trace_id}}
        result = await self.es.search(
            index="api-logs-*",
            query=query,
            size=100,
        )

        entries = []
        hits = result.get("hits", {}).get("hits", [])
        for hit in hits:
            src = hit.get("_source", {})
            entries.append(
                LogEntry(
                    id=hit.get("_id", ""),
                    service=src.get("service", ""),
                    level=src.get("level", "INFO"),
                    message=src.get("message", ""),
                    timestamp=datetime.fromisoformat(
                        src.get("@timestamp", datetime.utcnow().isoformat())
                        if src.get("@timestamp")
                        else datetime.utcnow().isoformat()
                    ),
                    trace_id=src.get("trace_id", ""),
                    status_code=int(src.get("status_code", 0)),
                    latency_ms=float(src.get("latency_ms", 0.0)),
                    endpoint=src.get("endpoint", ""),
                )
            )
        return entries
