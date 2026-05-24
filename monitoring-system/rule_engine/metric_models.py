from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MetricSnapshot:
    service: str
    error_rate: float
    p95_latency_ms: float
    request_volume: float
    db_errors: float
    gateway_timeouts: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
