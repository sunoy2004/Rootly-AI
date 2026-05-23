from prometheus_client import Counter, Histogram

UPSTREAM_FAILURES = Counter(
    "upstream_failures_total",
    "Upstream failures",
    ["service", "upstream"],
)

ORDER_LATENCY = Histogram(
    "order_processing_latency_seconds",
    "Order processing time",
    ["service"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)
