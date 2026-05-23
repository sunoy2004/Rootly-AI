from prometheus_client import Counter, Gauge

DB_ERRORS = Counter(
    "db_connection_errors_total",
    "DB connection errors",
    ["service"],
)

ACTIVE_DB_CONNECTIONS = Gauge(
    "active_db_connections",
    "Active DB connections",
    ["service"],
)

LOGIN_FAILURES = Counter(
    "login_failures_total",
    "Login failures",
    ["service"],
)
