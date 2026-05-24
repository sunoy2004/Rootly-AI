import json
import logging
from typing import Dict, Any, List

from llm_factory import get_llm
from incident_memory import IncidentMemory
from rate_limiter import AIRateLimiter
from context_builder import IncidentContextBuilder
from prompt_template import PROMPT, BATCH_PROMPT


logger = logging.getLogger(__name__)


def _normalize_result(raw: dict, context: dict) -> Dict[str, Any]:
    affected = raw.get("affected_services")
    if not affected:
        affected = context.get("affected_services", [])
    if isinstance(affected, str):
        affected = [affected]

    actions = raw.get("recommended_actions") or raw.get("debug_steps") or []

    debug_steps = raw.get("debug_steps") or []
    if not debug_steps and actions:
        debug_steps = []

    action_set = {a.lower().strip() for a in actions if isinstance(a, str)}
    debug_steps = [
        s for s in debug_steps
        if isinstance(s, str) and s.lower().strip() not in action_set
    ]

    if not debug_steps:
        svc = (affected or ["unknown"])[0] if affected else "unknown"
        debug_steps = [
            f"Search ERROR/WARNING logs for {svc} in Elasticsearch (last 30 min)",
            f"Inspect Jaeger traces for {svc} — look for slow or failed spans",
            f"Check Prometheus: error rate, p95 latency, DB errors for {svc}",
            "Review anomaly events and metric spikes on the dashboard",
            "Verify recent deployments or traffic pattern changes",
        ]

    return {
        "root_cause": raw.get("root_cause") or raw.get("probable_cause", "Unknown"),
        "severity": raw.get("severity", "WARNING"),
        "confidence": float(raw.get("confidence", 0.5)),
        "affected_services": affected,
        "recommended_actions": actions,
        "summary": raw.get("summary") or raw.get("detailed_explanation", ""),
        "evidence": raw.get("evidence", []),
        "debug_steps": debug_steps,
        "probable_cause": raw.get("root_cause") or raw.get("probable_cause", ""),
    }


class RootCauseAgent:
    def __init__(self):
        self.llm = get_llm()
        self.memory = IncidentMemory()
        self.rate_limiter = AIRateLimiter(max_per_minute=5)
        self.context_builder = IncidentContextBuilder()

    async def analyze(
        self, incident: dict, anomaly_event: dict
    ) -> Dict[str, Any]:
        similar = self.memory.retrieve_similar(incident.get("title", ""))

        context = await self.context_builder.build(
            incident, anomaly_event, similar
        )

        async def do_llm_call():
            error_logs_str = "\n".join(context["error_logs"]) or "No error logs available"
            similar_str = (
                "\n".join(
                    f"- {i.get('document', '')} (similarity: {i.get('similarity', 0):.2f})"
                    for i in similar
                )
                or "None found"
            )

            prompt = PROMPT.format_messages(
                service=context["service"],
                error_logs=error_logs_str,
                error_rate=context["error_rate"],
                p95_latency_ms=context["p95_latency_ms"],
                request_volume=context["request_volume"],
                db_errors=context["db_errors"],
                gateway_timeouts=context["gateway_timeouts"],
                cluster_representative=context["cluster_representative"],
                cluster_size=context["cluster_size"],
                affected_services=context["affected_services"],
                slowest_span=context["slowest_span"],
                first_error_span=context["first_error_span"],
                call_chain=context["call_chain"],
                similar_incidents=similar_str,
            )

            response = await self.llm.ainvoke(prompt)
            raw = response.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)
            return _normalize_result(parsed, context)

        result = await self.rate_limiter.run_with_limit(do_llm_call)
        logger.info(
            f"AI result for {context['service']}: {result['root_cause'][:80]} "
            f"(confidence={result['confidence']})"
        )
        return result

    async def analyze_batch(
        self,
        incident_stub: dict,
        representative_event: dict,
        batch_summary: dict,
    ) -> Dict[str, Any]:
        """Single Groq call for a batched cluster of anomalies."""
        service = representative_event.get("service", "unknown")
        similar = self.memory.retrieve_similar(incident_stub.get("title", ""))

        context = await self.context_builder.build(
            incident_stub, representative_event, similar
        )

        async def do_llm_call():
            similar_str = (
                "\n".join(
                    f"- {i.get('document', '')}" for i in similar
                )
                or "None found"
            )
            batch_str = json.dumps(batch_summary, indent=2, default=str)

            prompt = BATCH_PROMPT.format_messages(
                service=service,
                cluster_size=batch_summary.get("cluster_size", 1),
                affected_services=", ".join(
                    batch_summary.get("services", [service])
                ),
                batch_summary=batch_str,
                error_logs="\n".join(context["error_logs"][:10]) or "No error logs",
                error_rate=context["error_rate"],
                p95_latency_ms=context["p95_latency_ms"],
                db_errors=context["db_errors"],
                gateway_timeouts=context["gateway_timeouts"],
                similar_incidents=similar_str,
            )

            response = await self.llm.ainvoke(prompt)
            raw = response.content.strip().replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)
            ctx = {**context, "affected_services": batch_summary.get("services", [service])}
            return _normalize_result(parsed, ctx)

        result = await self.rate_limiter.run_with_limit(do_llm_call)
        logger.info(
            f"AI batch result for {service}: {result['root_cause'][:80]} "
            f"(cluster_size={batch_summary.get('cluster_size')})"
        )
        return result
