import logging
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest

from models import MetricSnapshot, AnomalyEvent
from prometheus_client import PrometheusClient


logger = logging.getLogger(__name__)


class IsolationForestDetector:
    def __init__(self):
        self.models: dict[str, IsolationForest] = {}
        self.is_trained: dict[str, bool] = {}

    async def train(self, service: str, prom_client: PrometheusClient):
        import asyncio

        start_minutes_ago = 10080
        step_seconds = 300

        service_clean = service.replace("-", "_")
        job_name = service

        error_rate_expr = (
            f'sum(rate(http_requests_total{{job="{job_name}",status=~"5.."}}[5m]))'
            f' / sum(rate(http_requests_total{{job="{job_name}"}}[5m]))'
        )
        p95_latency_expr = (
            f'histogram_quantile(0.95, '
            f'sum(rate(http_request_duration_seconds_bucket{{job="{job_name}"}}[5m])) by (le)) * 1000'
        )
        request_volume_expr = f'sum(rate(http_requests_total{{job="{job_name}"}}[5m]))'
        db_errors_expr = f'sum(rate(db_connection_errors_total{{service="{service}"}}[5m]))'
        gateway_timeouts_expr = f'sum(rate(payment_gateway_timeouts_total{{service="{service}"}}[5m]))'

        (
            error_rate_data,
            p95_latency_data,
            request_volume_data,
            db_errors_data,
            gateway_timeouts_data,
        ) = await asyncio.gather(
            prom_client.query_range(error_rate_expr, start_minutes_ago, step_seconds),
            prom_client.query_range(p95_latency_expr, start_minutes_ago, step_seconds),
            prom_client.query_range(request_volume_expr, start_minutes_ago, step_seconds),
            prom_client.query_range(db_errors_expr, start_minutes_ago, step_seconds),
            prom_client.query_range(gateway_timeouts_expr, start_minutes_ago, step_seconds),
        )

        data_by_ts = {}
        for ts, val in error_rate_data:
            data_by_ts.setdefault(ts, {})["error_rate"] = val
        for ts, val in p95_latency_data:
            data_by_ts.setdefault(ts, {})["p95_latency_ms"] = val
        for ts, val in request_volume_data:
            data_by_ts.setdefault(ts, {})["request_volume"] = val
        for ts, val in db_errors_data:
            data_by_ts.setdefault(ts, {})["db_errors"] = val
        for ts, val in gateway_timeouts_data:
            data_by_ts.setdefault(ts, {})["gateway_timeouts"] = val

        X = []
        for ts, vals in sorted(data_by_ts.items()):
            row = [
                vals.get("error_rate", 0.0),
                vals.get("p95_latency_ms", 0.0),
                vals.get("request_volume", 0.0),
                vals.get("db_errors", 0.0),
                vals.get("gateway_timeouts", 0.0),
            ]
            if any(v != 0 for v in row):
                X.append(row)

        if len(X) < 50:
            logger.warning(f"Insufficient training data for {service}: {len(X)} rows")
            return

        X = np.array(X)
        model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        model.fit(X)

        self.models[service] = model
        self.is_trained[service] = True
        logger.info(f"Trained IF model for {service}")

    def detect(self, snapshot: MetricSnapshot) -> Optional[AnomalyEvent]:
        if not self.is_trained.get(snapshot.service):
            return None

        X = np.array(
            [
                [
                    snapshot.error_rate,
                    snapshot.p95_latency_ms,
                    snapshot.request_volume,
                    snapshot.db_errors,
                    snapshot.gateway_timeouts,
                ]
            ]
        )

        model = self.models[snapshot.service]
        prediction = model.predict(X)[0]
        score = model.decision_function(X)[0]

        if prediction == -1:
            severity = "CRITICAL" if score < -0.2 else "WARNING"
            return AnomalyEvent(
                service=snapshot.service,
                metric="multivariate",
                current_value=float(score),
                severity=severity,
                detector="isolation_forest",
                anomaly_score=float(score),
                snapshot=snapshot,
            )
        return None
