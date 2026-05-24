import logging
import os
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")


def _normalize_log(src: dict) -> dict:
    level = src.get("level") or src.get("levelname", "INFO")
    ts = src.get("@timestamp") or src.get("timestamp")
    status = src.get("status_code", 0)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    latency = src.get("latency_ms", 0)
    try:
        latency = float(latency)
    except (TypeError, ValueError):
        latency = 0.0
    return {
        "timestamp": ts,
        "service": src.get("service", ""),
        "level": str(level).upper(),
        "endpoint": src.get("endpoint", ""),
        "status_code": status,
        "latency_ms": latency,
        "message": src.get("message", ""),
        "trace_id": src.get("trace_id", "") or "",
        "span_id": src.get("span_id", "") or "",
    }


def _level_clause(level: str) -> dict:
    level_up = level.upper()
    return {
        "bool": {
            "should": [
                {"term": {"level.keyword": level_up}},
                {"term": {"levelname.keyword": level_up}},
                {"match": {"level": level_up}},
                {"match": {"levelname": level_up}},
            ],
            "minimum_should_match": 1,
        }
    }


async def search_logs(
    service: Optional[str] = None,
    level: Optional[str] = None,
    search_text: Optional[str] = None,
    limit: int = 50,
) -> List[dict]:
    must = []
    if service:
        must.append({
            "bool": {
                "should": [
                    {"term": {"service.keyword": service}},
                    {"match": {"service": service}},
                ],
                "minimum_should_match": 1,
            }
        })
    if level:
        must.append(_level_clause(level))
    if search_text:
        must.append({"match": {"message": search_text}})

    query = {"bool": {"must": must}} if must else {"match_all": {}}

    body = {
        "size": limit,
        "sort": [{"@timestamp": {"order": "desc", "unmapped_type": "date"}}],
        "query": query,
    }

    logs = []
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.post(f"{ES_URL}/api-logs-*/_search", json=body)
            resp.raise_for_status()
            data = resp.json()
            for hit in data.get("hits", {}).get("hits", []):
                logs.append(_normalize_log(hit.get("_source", {})))
        except Exception as exc:
            logger.warning(f"Elasticsearch log search failed: {exc}")

    return logs
