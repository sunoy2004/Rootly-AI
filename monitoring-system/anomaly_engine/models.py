from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class MetricSnapshot:
    service: str
    error_rate: float
    p95_latency_ms: float
    request_volume: float
    db_errors: float
    gateway_timeouts: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AnomalyEvent:
    id: str = field(default_factory=lambda: str(uuid4()))
    service: str = ""
    metric: str = ""
    current_value: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    z_score: Optional[float] = None
    anomaly_score: Optional[float] = None
    severity: str = "WARNING"
    detector: str = ""
    snapshot: Optional[MetricSnapshot] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        if self.snapshot:
            data["snapshot"] = asdict(self.snapshot)
            data["snapshot"]["timestamp"] = self.snapshot.timestamp.isoformat()
        return data
