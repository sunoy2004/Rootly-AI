import logging
import os
from typing import Optional

import yaml

from models import Rule, RuleCondition, RuleMatch
from metric_models import MetricSnapshot


logger = logging.getLogger(__name__)


class RuleEvaluator:
    def __init__(self):
        self.rules: list[Rule] = []
        self._load_rules()

    def _load_rules(self):
        rules_path = os.path.join(os.path.dirname(__file__), "rules.yaml")
        with open(rules_path, "r") as f:
            data = yaml.safe_load(f)

        for rule_def in data.get("rules", []):
            conditions = []
            for cond in rule_def.get("conditions", []):
                conditions.append(
                    RuleCondition(
                        field=cond["field"],
                        operator=cond["operator"],
                        threshold=float(cond["threshold"]),
                        service=cond.get("service"),
                    )
                )

            self.rules.append(
                Rule(
                    name=rule_def["name"],
                    conditions=conditions,
                    logic=rule_def.get("logic", "SINGLE"),
                    diagnosis=rule_def.get("diagnosis", "").strip(),
                    recommendation=rule_def.get("recommendation", "").strip(),
                    confidence=float(rule_def.get("confidence", 0.5)),
                    severity=rule_def.get("severity", "WARNING"),
                )
            )

        logger.info(f"Loaded {len(self.rules)} rules")

    @staticmethod
    def evaluate_operator(val: float, op: str, threshold: float) -> bool:
        op = op.lower()
        if op == "gt":
            return val > threshold
        elif op == "lt":
            return val < threshold
        elif op == "eq":
            return abs(val - threshold) < 0.001
        elif op == "gte":
            return val >= threshold
        elif op == "lte":
            return val <= threshold
        return False

    def evaluate(
        self,
        anomaly_event: dict,
        snapshots: dict[str, MetricSnapshot],
    ) -> Optional[RuleMatch]:
        service = anomaly_event.get("service", "")
        snapshot = snapshots.get(service)

        for rule in self.rules:
            matched_conditions = []

            for condition in rule.conditions:
                if condition.service:
                    target_snap = snapshots.get(condition.service)
                    if not target_snap:
                        continue
                    val = getattr(target_snap, condition.field, 0.0)
                else:
                    if not snapshot:
                        continue
                    val = getattr(snapshot, condition.field, 0.0)

                if self.evaluate_operator(val, condition.operator, condition.threshold):
                    matched_conditions.append(
                        f"{condition.field} {condition.operator} "
                        f"{condition.threshold} (actual: {val:.3f})"
                    )

            if rule.logic == "AND":
                if len(matched_conditions) == len(rule.conditions) and len(rule.conditions) > 0:
                    return RuleMatch(
                        rule_name=rule.name,
                        diagnosis=rule.diagnosis,
                        recommendation=rule.recommendation,
                        confidence=rule.confidence,
                        severity=rule.severity,
                        matched_conditions=matched_conditions,
                        service=service,
                        anomaly_event=anomaly_event,
                    )
            else:
                if matched_conditions:
                    return RuleMatch(
                        rule_name=rule.name,
                        diagnosis=rule.diagnosis,
                        recommendation=rule.recommendation,
                        confidence=rule.confidence,
                        severity=rule.severity,
                        matched_conditions=matched_conditions,
                        service=service,
                        anomaly_event=anomaly_event,
                    )

        return None
