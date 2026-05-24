from datetime import datetime, timedelta
from typing import List, Tuple

import httpx

from metric_models import MetricSnapshot


class PrometheusClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def query_instant(self, expr: str) -> float:
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": expr},
            )
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "success":
                return 0.0
            result = data.get("data", {}).get("result", [])
            if not result:
                return 0.0
            value = result[0].get("value", [])
            if len(value) < 2:
                return 0.0
            return float(value[1])
        except Exception:
            return 0.0

    async def query_range(
        self, expr: str, start_minutes_ago: int, step_seconds: int = 60
    ) -> List[Tuple[datetime, float]]:
        try:
            end = datetime.utcnow()
            start = end - timedelta(minutes=start_minutes_ago)
            response = await self.client.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": expr,
                    "start": int(start.timestamp()),
                    "end": int(end.timestamp()),
                    "step": step_seconds,
                },
            )
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "success":
                return []
            result = data.get("data", {}).get("result", [])
            values = []
            if result and "values" in result[0]:
                for ts, val in result[0]["values"]:
                    values.append((datetime.fromtimestamp(float(ts)), float(val)))
            return values
        except Exception:
            return []

    async def get_full_snapshot(self, service: str) -> MetricSnapshot:
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

        import asyncio

        (
            error_rate,
            p95_latency_ms,
            request_volume,
            db_errors,
            gateway_timeouts,
        ) = await asyncio.gather(
            self.query_instant(error_rate_expr),
            self.query_instant(p95_latency_expr),
            self.query_instant(request_volume_expr),
            self.query_instant(db_errors_expr),
            self.query_instant(gateway_timeouts_expr),
        )

        return MetricSnapshot(
            service=service,
            error_rate=error_rate,
            p95_latency_ms=p95_latency_ms,
            request_volume=request_volume,
            db_errors=db_errors,
            gateway_timeouts=gateway_timeouts,
        )
