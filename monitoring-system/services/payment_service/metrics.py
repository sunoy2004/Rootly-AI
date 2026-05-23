from prometheus_client import Counter, Histogram

GATEWAY_TIMEOUTS = Counter(
    "payment_gateway_timeouts_total",
    "Gateway timeouts",
    ["service"],
)

PAYMENT_DECLINES = Counter(
    "payment_declines_total",
    "Payment declines",
    ["service"],
)

GATEWAY_RESPONSE_TIME = Histogram(
    "gateway_response_time_seconds",
    "Gateway response time",
    ["service"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)
