from collections import deque
import statistics
from typing import Optional, List

from models import MetricSnapshot, AnomalyEvent


class ZScoreDetector:
    def __init__(self):
        self.windows: dict[str, deque] = {}

    def detect(
        self, service: str, metric: str, value: float, snapshot: MetricSnapshot
    ) -> Optional[AnomalyEvent]:
        key = f"{service}:{metric}"
        if key not in self.windows:
            self.windows[key] = deque(maxlen=30)
        self.windows[key].append(value)

        window = list(self.windows[key])
        if len(window) < 10:
            return None

        mean = statistics.mean(window)
        std = statistics.stdev(window)

        if std == 0:
            return None

        z = (value - mean) / std

        if z > 3:
            severity = "CRITICAL"
        elif z > 2:
            severity = "WARNING"
        else:
            return None

        return AnomalyEvent(
            service=service,
            metric=metric,
            current_value=value,
            mean=mean,
            std=std,
            z_score=z,
            severity=severity,
            detector="zscore",
            snapshot=snapshot,
        )

    def detect_all(self, snapshot: MetricSnapshot) -> List[AnomalyEvent]:
        results = []
        metrics = [
            ("error_rate", snapshot.error_rate),
            ("p95_latency_ms", snapshot.p95_latency_ms),
            ("db_errors", snapshot.db_errors),
            ("gateway_timeouts", snapshot.gateway_timeouts),
        ]
        for metric, value in metrics:
            event = self.detect(snapshot.service, metric, value, snapshot)
            if event:
                results.append(event)
        return results
