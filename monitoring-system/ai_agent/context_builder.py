import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import httpx


logger = logging.getLogger(__name__)


PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
JAEGER_URL = os.getenv("JAEGER_URL", "http://jaeger:16686")
INCIDENT_MANAGER_URL = os.getenv("INCIDENT_MANAGER_URL", "http://incident-manager:8007")


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

    async def get_full_snapshot(self, service: str):
        from models import MetricSnapshot

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
            timestamp=datetime.utcnow(),
        )


class ElasticsearchClient:
    def __init__(self, host: str):
        self.host = host.rstrip("/")

    async def get_errors_by_service(self, service: str, minutes: int = 30) -> List[dict]:
        from models import LogEntry

        query = {
            "bool": {
                "must": [
                    {"term": {"level": "ERROR"}},
                    {"term": {"service": service}},
                    {"range": {"@timestamp": {"gte": f"now-{minutes}m"}}},
                ]
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.host}/api-logs-*/_search",
                    params={
                        "source": str(query),
                        "size": 10,
                        "sort": "@timestamp:desc",
                    },
                )
                data = response.json()
                entries = []
                for hit in data.get("hits", {}).get("hits", []):
                    src = hit.get("_source", {})
                    entries.append(
                        LogEntry(
                            id=hit.get("_id", ""),
                            service=src.get("service", ""),
                            level=src.get("level", "ERROR"),
                            message=src.get("message", ""),
                            timestamp=datetime.fromisoformat(
                                src.get("@timestamp", datetime.utcnow().isoformat())
                            )
                            if src.get("@timestamp")
                            else datetime.utcnow(),
                            trace_id=src.get("trace_id", ""),
                            status_code=int(src.get("status_code", 0)),
                            latency_ms=float(src.get("latency_ms", 0.0)),
                            endpoint=src.get("endpoint", ""),
                        )
                    )
                return entries
            except Exception:
                return []


class IncidentContextBuilder:
    def __init__(self):
        self.prom_client = PrometheusClient(PROMETHEUS_URL)
        self.es_client = ElasticsearchClient(ES_URL)

    async def build(
        self,
        incident: dict,
        anomaly_event: dict,
        similar_incidents: List[dict],
    ) -> dict:
        service = incident.get("affected_services", [""])[0]

        error_logs, snapshot, traces = await asyncio.gather(
            self.es_client.get_errors_by_service(service, minutes=30),
            self.prom_client.get_full_snapshot(service),
            self._fetch_traces(service),
        )

        cluster = None
        if incident.get("cluster_id"):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{INCIDENT_MANAGER_URL}/clusters",
                        params={"status": "open", "limit": 1},
                    )
                    clusters = resp.json()
                    for c in clusters:
                        if c.get("id") == incident.get("cluster_id"):
                            cluster = c
                            break
            except Exception:
                pass

        from confidence_scorer import ConfidenceScorer
        pre_confidence = ConfidenceScorer().score(
            anomaly_event, cluster, similar_incidents
        )

        error_log_messages = [e.message for e in error_logs[:10]]

        return {
            "service": service,
            "error_logs": error_log_messages,
            "error_rate": snapshot.error_rate,
            "p95_latency_ms": snapshot.p95_latency_ms,
            "request_volume": snapshot.request_volume,
            "db_errors": snapshot.db_errors,
            "gateway_timeouts": snapshot.gateway_timeouts,
            "cluster_representative": cluster.get("representative_message")
            if cluster
            else "N/A",
            "cluster_size": cluster.get("member_count", 0) if cluster else 0,
            "affected_services": cluster.get("affected_services", [service])
            if cluster
            else [service],
            "slowest_span": traces.get("slowest", "N/A"),
            "first_error_span": traces.get("first_error", "N/A"),
            "call_chain": traces.get("chain", "N/A"),
            "similar_incidents": similar_incidents,
            "pre_confidence": pre_confidence,
            "metric_agreement": min(
                (
                    1 if snapshot.error_rate > 0.1 else 0
                    + (1 if snapshot.p95_latency_ms > 1000 else 0)
                    + (1 if snapshot.db_errors > 0.1 else 0)
                    + (1 if snapshot.gateway_timeouts > 0.1 else 0)
                )
                / 4.0,
                1.0,
            ),
            "cluster_strength": min(
                (cluster.get("member_count", 0) if cluster else 0) / 50.0, 1.0
            ),
            "memory_similarity": max(
                (i.get("similarity", 0) for i in similar_incidents), default=0.0
            ),
        }

    async def _fetch_traces(self, service: str) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{JAEGER_URL}/api/traces",
                    params={
                        "service": service,
                        "limit": 5,
                        "tags": '{"error":"true"}',
                    },
                )
                data = resp.json()

                traces = data.get("data", [])
                if not traces:
                    return {"slowest": "N/A", "first_error": "N/A", "chain": "N/A"}

                slowest_span = None
                slowest_duration = 0
                first_error = None
                chain = []

                for trace in traces:
                    spans = trace.get("spans", [])
                    for span in spans:
                        duration = span.get("duration", 0)
                        if duration > slowest_duration:
                            slowest_duration = duration
                            slowest_span = span.get("operationName", "unknown")

                        tags = {t.get("key"): t.get("value") for t in span.get("tags", [])}
                        if tags.get("error") and not first_error:
                            first_error = span.get("operationName", "unknown")

                        if span.get("serviceName") not in chain:
                            chain.append(span.get("serviceName", ""))

                return {
                    "slowest": slowest_span or "N/A",
                    "first_error": first_error or "N/A",
                    "chain": " -> ".join([s for s in chain if s]) or "N/A",
                }
        except Exception:
            return {"slowest": "N/A", "first_error": "N/A", "chain": "N/A"}
