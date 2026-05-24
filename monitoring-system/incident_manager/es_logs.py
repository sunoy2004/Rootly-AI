import logging
import os
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")


def _normalize_log(src: dict) -> dict:
    level = src.get("level") or src.get("levelname", "INFO")
    ts = src.get("@timestamp") or src.get("timestamp")
    return {
        "timestamp": ts,
        "service": src.get("service", ""),
        "level": level,
        "endpoint": src.get("endpoint", ""),
        "status_code": src.get("status_code", 0),
        "latency_ms": src.get("latency_ms", 0),
        "message": src.get("message", ""),
        "trace_id": src.get("trace_id", ""),
        "span_id": src.get("span_id", ""),
    }


async def search_logs(
    service: Optional[str] = None,
    level: Optional[str] = None,
    search_text: Optional[str] = None,
    limit: int = 50,
) -> List[dict]:
    must = []
    if service:
        must.append({"match": {"service": service}})
    if level:
        must.append({
            "bool": {
                "should": [
                    {"term": {"level.keyword": level}},
                    {"term": {"levelname.keyword": level}},
                ],
                "minimum_should_match": 1,
            }
        })
    if search_text:
        must.append({"match": {"message": search_text}})

    query = {"bool": {"must": must}} if must else {"match_all": {}}

    body = {
        "size": limit,
        "sort": [{"@timestamp": {"order": "desc", "unmapped_type": "date"}}],
        "query": query,
    }

    logs = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{ES_URL}/api-logs-*/_search", json=body)
            resp.raise_for_status()
            data = resp.json()
            for hit in data.get("hits", {}).get("hits", []):
                logs.append(_normalize_log(hit.get("_source", {})))
        except Exception as exc:
            logger.warning(f"Elasticsearch log search failed: {exc}")

    return logs
