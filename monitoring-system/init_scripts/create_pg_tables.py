import sys
import time
import psycopg2

PG_DSN = "host=postgres dbname=monitoring user=monitor password=monitor123"
MAX_RETRIES = 10
RETRY_SLEEP = 5

DDL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(100) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    current_value FLOAT NOT NULL,
    mean FLOAT NOT NULL,
    std FLOAT NOT NULL,
    z_score FLOAT,
    anomaly_score FLOAT,
    severity VARCHAR(20) NOT NULL,
    detector VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS failure_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    representative_message TEXT NOT NULL,
    member_count INTEGER NOT NULL DEFAULT 1,
    affected_services TEXT[] NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    severity VARCHAR(20) NOT NULL,
    affected_services TEXT[] NOT NULL,
    cluster_id UUID REFERENCES failure_clusters(id),
    root_cause TEXT,
    confidence FLOAT,
    source VARCHAR(20) NOT NULL,
    similar_incident_ids UUID[],
    alert_sent BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id),
    root_cause TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    affected_services TEXT[] NOT NULL DEFAULT '{}',
    recommended_actions TEXT[] NOT NULL DEFAULT '{}',
    summary TEXT,
    raw_response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_analyses_incident_id
    ON ai_analyses (incident_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_anomalies_service_metric_ts
    ON anomalies (service, metric, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_failure_clusters_status_last_seen
    ON failure_clusters (status, last_seen DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_status_created_at
    ON incidents (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_affected_services
    ON incidents USING GIN (affected_services);
"""


def main() -> None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            conn = psycopg2.connect(PG_DSN)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(DDL)
            cur.close()
            conn.close()
            print("PostgreSQL tables and indexes created successfully.")
            return
        except psycopg2.OperationalError as exc:
            print(f"Attempt {attempt}/{MAX_RETRIES}: PG not ready yet ({exc})")
        except Exception as exc:
            print(f"Attempt {attempt}/{MAX_RETRIES}: Unexpected error ({exc})")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_SLEEP)

    print("Failed to connect to PostgreSQL after max retries.")
    sys.exit(1)


if __name__ == "__main__":
    main()
