from langchain_core.prompts import ChatPromptTemplate


SYSTEM = """You are a senior Site Reliability Engineer with 10 years of experience debugging distributed systems. You analyze API failures and produce precise, evidence-based root cause analysis.

Rules:
1. Only state conclusions supported by evidence.
2. Do not speculate beyond the data provided.
3. Be concise. Bullet points over paragraphs.
4. Always provide a confidence score 0.0 to 1.0.
5. If evidence is ambiguous, score 0.5 or lower.
"""

HUMAN = """Analyze this incident and provide root cause analysis.

SERVICE: {service}

RECENT ERROR LOGS (last 10):
{error_logs}

CURRENT METRICS:
- Error rate: {error_rate:.4f} errors/sec
- p95 Latency: {p95_latency_ms:.0f}ms
- Request volume: {request_volume:.2f} req/sec
- DB errors: {db_errors:.4f}/sec
- Gateway timeouts: {gateway_timeouts:.4f}/sec

FAILURE CLUSTER:
- Representative error: {cluster_representative}
- Total occurrences: {cluster_size}
- Affected services: {affected_services}

DISTRIBUTED TRACE SUMMARY:
- Slowest span: {slowest_span}
- First error span: {first_error_span}
- Call chain: {call_chain}

SIMILAR PAST INCIDENTS:
{similar_incidents}

PRE-COMPUTED CONFIDENCE: {pre_confidence}
(metric_agreement={metric_agreement:.2f}, cluster_strength={cluster_strength:.2f}, memory_similarity={memory_similarity:.2f})

Respond ONLY with this exact JSON, no other text:
{{
  "probable_cause": "one sentence",
  "detailed_explanation": "2-3 sentences",
  "evidence": ["point1", "point2", "point3"],
  "debug_steps": ["step1", "step2", "step3"],
  "confidence": 0.0,
  "confidence_reasoning": "brief explanation",
  "estimated_impact": "low/medium/high",
  "similar_to_past_incident": false,
  "past_incident_reference": null
}}"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", HUMAN),
    ]
)
