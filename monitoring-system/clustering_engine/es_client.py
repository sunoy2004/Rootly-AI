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
                    {
                        "bool": {
                            "should": [
                                {"term": {"level.keyword": "ERROR"}},
                                {"term": {"levelname.keyword": "ERROR"}},
                                {"match": {"level": "ERROR"}},
                                {"match": {"levelname": "ERROR"}},
                                {"term": {"level.keyword": "WARNING"}},
                                {"match": {"level": "WARNING"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
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
            entries.append(self._to_entry(hit.get("_id", ""), src))
        return entries

    def _to_entry(self, doc_id: str, src: dict) -> LogEntry:
        ts_raw = src.get("@timestamp") or datetime.utcnow().isoformat()
        if isinstance(ts_raw, str):
            ts_raw = ts_raw.replace("Z", "+00:00")
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            ts = datetime.utcnow()

        return LogEntry(
            id=doc_id,
            service=src.get("service", ""),
            level=src.get("level") or src.get("levelname", "ERROR"),
            message=src.get("message", ""),
            timestamp=ts,
            trace_id=src.get("trace_id", "") or "",
            status_code=int(src.get("status_code", 0) or 0),
            latency_ms=float(src.get("latency_ms", 0) or 0),
            endpoint=src.get("endpoint", ""),
        )

    async def get_errors_by_service(
        self, service: str, minutes: int = 30
    ) -> List[LogEntry]:
        query = {
            "bool": {
                "must": [
                    {"match": {"service": service}},
                    {
                        "bool": {
                            "should": [
                                {"term": {"level.keyword": "ERROR"}},
                                {"match": {"level": "ERROR"}},
                                {"match": {"levelname": "ERROR"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
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

        return [
            self._to_entry(hit.get("_id", ""), hit.get("_source", {}))
            for hit in result.get("hits", {}).get("hits", [])
        ]

    async def get_logs_by_trace_id(self, trace_id: str) -> List[LogEntry]:
        query = {"term": {"trace_id.keyword": trace_id}}
        result = await self.es.search(
            index="api-logs-*",
            query=query,
            size=100,
        )

        return [
            self._to_entry(hit.get("_id", ""), hit.get("_source", {}))
            for hit in result.get("hits", {}).get("hits", [])
        ]
