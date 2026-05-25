"""Absolute metric thresholds — fires during storm bursts before Z-score window warms up."""

from typing import List

from models import MetricSnapshot, AnomalyEvent

THRESHOLDS = {
    "error_rate": (0.01, 0.03),       # (WARNING, CRITICAL)
    "p95_latency_ms": (150, 500),
    "db_errors": (0.005, 0.02),
    "gateway_timeouts": (0.01, 0.04),
}


def detect_thresholds(snapshot: MetricSnapshot) -> List[AnomalyEvent]:
    events = []
    metrics = {
        "error_rate": snapshot.error_rate,
        "p95_latency_ms": snapshot.p95_latency_ms,
        "db_errors": snapshot.db_errors,
        "gateway_timeouts": snapshot.gateway_timeouts,
    }

    for metric, value in metrics.items():
        warn, crit = THRESHOLDS[metric]
        if value >= crit:
            severity = "CRITICAL"
        elif value >= warn:
            severity = "WARNING"
        else:
            continue

        events.append(
            AnomalyEvent(
                service=snapshot.service,
                metric=metric,
                current_value=value,
                mean=value,
                std=0.0,
                z_score=None,
                anomaly_score=None,
                severity=severity,
                detector="threshold",
                snapshot=snapshot,
            )
        )
    return events
