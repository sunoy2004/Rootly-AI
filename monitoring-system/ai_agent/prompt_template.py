from langchain_core.prompts import ChatPromptTemplate


SYSTEM = """You are a senior Site Reliability Engineer specializing in distributed systems and API failures.

Analyze logs, metrics, traces, anomalies, and service dependencies.

Return ONLY valid JSON matching the schema below. Do not speculate beyond available evidence."""

HUMAN = """Analyze this incident.

SERVICE: {service}

RECENT ERROR LOGS:
{error_logs}

CURRENT METRICS:
- Error rate: {error_rate:.4f}/sec
- p95 Latency: {p95_latency_ms:.0f}ms
- Request volume: {request_volume:.2f}/sec
- DB errors: {db_errors:.4f}/sec
- Gateway timeouts: {gateway_timeouts:.4f}/sec

FAILURE CLUSTER:
- Representative: {cluster_representative}
- Size: {cluster_size}
- Services: {affected_services}

TRACE SUMMARY:
- Slowest span: {slowest_span}
- First error span: {first_error_span}
- Call chain: {call_chain}

SIMILAR PAST INCIDENTS:
{similar_incidents}

Respond ONLY with this JSON:
{{
  "root_cause": "one sentence probable root cause",
  "severity": "WARNING or CRITICAL",
  "confidence": 0.0,
  "affected_services": ["service-a"],
  "recommended_actions": ["action1", "action2", "action3"],
  "summary": "2-3 sentence summary with evidence",
  "evidence": ["point1", "point2"],
  "debug_steps": ["step1", "step2"]
}}"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", HUMAN),
    ]
)

BATCH_HUMAN = """Analyze this BATCHED cluster of related anomalies (do NOT analyze each event separately).

PRIMARY SERVICE: {service}
CLUSTER SIZE: {cluster_size} events
AFFECTED SERVICES: {affected_services}

BATCH SUMMARY:
{batch_summary}

RECENT ERROR LOGS (sample):
{error_logs}

CURRENT METRICS:
- Error rate: {error_rate:.4f}/sec
- p95 Latency: {p95_latency_ms:.0f}ms
- DB errors: {db_errors:.4f}/sec
- Gateway timeouts: {gateway_timeouts:.4f}/sec

SIMILAR PAST INCIDENTS:
{similar_incidents}

Respond ONLY with this JSON:
{{
  "root_cause": "one sentence probable root cause for the whole cluster",
  "severity": "WARNING or CRITICAL",
  "confidence": 0.0,
  "affected_services": ["service-a"],
  "recommended_actions": ["action1", "action2"],
  "summary": "2-3 sentence summary",
  "evidence": ["point1", "point2"]
}}"""

BATCH_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", BATCH_HUMAN),
    ]
)
