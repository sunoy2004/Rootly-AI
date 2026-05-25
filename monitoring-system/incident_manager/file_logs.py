import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

LOG_DIR = os.getenv("LOG_DIR", "/logs")
LOG_MAX_AGE_MINUTES = int(os.getenv("LOG_MAX_AGE_MINUTES", "30"))
SERVICE_FILES = {
    "user-service": "user-service.log",
    "order-service": "order-service.log",
    "payment-service": "payment-service.log",
}


def _normalize_from_file(obj: dict) -> dict:
    level = obj.get("level") or obj.get("levelname", "INFO")
    return {
        "timestamp": obj.get("timestamp") or obj.get("@timestamp"),
        "service": obj.get("service", ""),
        "level": str(level).upper(),
        "endpoint": obj.get("endpoint", ""),
        "status_code": int(obj.get("status_code") or 0),
        "latency_ms": float(obj.get("latency_ms") or 0),
        "message": obj.get("message", ""),
        "trace_id": obj.get("trace_id", "") or "",
        "span_id": obj.get("span_id", "") or "",
    }


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_recent(entry: dict, max_age: timedelta) -> bool:
    ts = _parse_ts(entry.get("timestamp"))
    if not ts:
        return True
    return datetime.now(timezone.utc) - ts <= max_age


def read_file_logs(
    service: Optional[str] = None,
    level: Optional[str] = None,
    search_text: Optional[str] = None,
    limit: int = 50,
) -> List[dict]:
    """Tail JSON log files from the shared /logs volume when Elasticsearch is empty or slow."""
    targets = []
    if service and service in SERVICE_FILES:
        targets.append((service, Path(LOG_DIR) / SERVICE_FILES[service]))
    else:
        for svc, fname in SERVICE_FILES.items():
            targets.append((svc, Path(LOG_DIR) / fname))

    level_up = level.upper() if level else None
    search_lower = search_text.lower() if search_text else None
    max_age = timedelta(minutes=LOG_MAX_AGE_MINUTES)
    collected: List[dict] = []

    for svc, path in targets:
        if not path.is_file():
            continue
        try:
            with open(path, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 256_000))
                chunk = fh.read().decode("utf-8", errors="replace")
        except OSError as exc:
            logger.debug(f"Cannot read {path}: {exc}")
            continue

        for line in reversed(chunk.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not obj.get("service"):
                obj["service"] = svc
            entry = _normalize_from_file(obj)
            if not _is_recent(entry, max_age):
                continue
            if level_up and entry["level"] != level_up:
                continue
            if search_lower and search_lower not in (entry.get("message") or "").lower():
                continue
            collected.append(entry)
            if len(collected) >= limit * 3:
                break

    collected.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return collected[:limit]
