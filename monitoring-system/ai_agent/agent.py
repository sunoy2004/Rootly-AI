import json
import logging
from typing import Dict, Any

from llm_factory import get_llm
from incident_memory import IncidentMemory
from rate_limiter import AIRateLimiter
from context_builder import IncidentContextBuilder
from prompt_template import PROMPT


logger = logging.getLogger(__name__)


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
                pre_confidence=context["pre_confidence"],
                metric_agreement=context["metric_agreement"],
                cluster_strength=context["cluster_strength"],
                memory_similarity=context["memory_similarity"],
            )

            response = await self.llm.ainvoke(prompt)
            raw = response.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)

        result = await self.rate_limiter.run_with_limit(do_llm_call)
        return result
