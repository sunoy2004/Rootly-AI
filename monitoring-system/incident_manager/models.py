from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentSeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class IncidentSource(str, Enum):
    RULE_ENGINE = "RULE_ENGINE"
    AI_AGENT = "AI_AGENT"


class IncidentResponse(BaseModel):
    id: str
    title: str
    status: IncidentStatus
    severity: IncidentSeverity
    affected_services: List[str]
    root_cause: Optional[str]
    confidence: Optional[float]
    source: IncidentSource
    alert_sent: bool
    created_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]


class UpdateIncidentRequest(BaseModel):
    status: IncidentStatus
    resolution_notes: Optional[str] = None
