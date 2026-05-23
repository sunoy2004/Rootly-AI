from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class LogEntry:
    id: str
    service: str
    level: str
    message: str
    timestamp: datetime
    trace_id: str
    status_code: int
    latency_ms: float
    endpoint: str


@dataclass
class MetricSnapshot:
    service: str
    error_rate: float
    p95_latency_ms: float
    request_volume: float
    db_errors: float
    gateway_timeouts: float
    timestamp: datetime
