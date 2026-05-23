from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


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
class FailureCluster:
    cluster_id: str = field(default_factory=lambda: str(uuid4()))
    representative_message: str = ""
    member_count: int = 0
    member_trace_ids: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
