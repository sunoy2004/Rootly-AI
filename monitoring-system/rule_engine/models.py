from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List


@dataclass
class RuleCondition:
    field: str
    operator: str
    threshold: float
    service: Optional[str] = None


@dataclass
class Rule:
    name: str
    conditions: List[RuleCondition]
    logic: str
    diagnosis: str
    recommendation: str
    confidence: float
    severity: str


@dataclass
class RuleMatch:
    rule_name: str
    diagnosis: str
    recommendation: str
    confidence: float
    severity: str
    matched_conditions: List[str]
    service: str
    anomaly_event: dict
