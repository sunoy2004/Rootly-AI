# Rootly-AI — System Architecture & Implementation Guide

This document is the single technical reference for the Rootly-AI monitoring platform. It covers topology, service responsibilities, data flows, algorithms, storage schemas, Redis channels, API surface, directory layout, and operational behavior as implemented in the codebase.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Tier Architecture](#2-tier-architecture)
3. [Docker Services Reference](#3-docker-services-reference)
4. [Directory Structure](#4-directory-structure)
5. [Telemetry Pipeline](#5-telemetry-pipeline)
6. [Operations Event Pipeline](#6-operations-event-pipeline)
7. [Redis Event Bus](#7-redis-event-bus)
8. [Component Deep Dives](#8-component-deep-dives)
9. [Algorithms & Detection Logic](#9-algorithms--detection-logic)
10. [Database Schemas](#10-database-schemas)
11. [Incident Manager API](#11-incident-manager-api)
12. [Dashboard Architecture](#12-dashboard-architecture)
13. [Environment Configuration](#13-environment-configuration)
14. [Zero-Traffic Filtering](#14-zero-traffic-filtering)
15. [Deployment & Development Notes](#15-deployment--development-notes)

---

## 1. System Overview

Rootly-AI is a five-tier observability and incident response system:

```mermaid
flowchart TB
    subgraph T1 ["Tier 1 — Monitored Application"]
        LS[load_simulator.py]
        US[user-service :8001]
        OS[order-service :8002]
        PS[payment-service :8003]
    end

    subgraph T2 ["Tier 2 — Observability Infrastructure"]
        PROM[(Prometheus :9090)]
        FB[Fluent Bit]
        ES[(Elasticsearch :9200)]
        JG[Jaeger :16686 / OTLP :4317]
        GF[Grafana :3001]
    end

    subgraph T3 ["Tier 3 — Operations & AI Engines"]
        AE[Anomaly Engine :8004]
        RE[Rule Engine :8015]
        CE[Clustering Engine :8006]
        IM[Incident Manager :8013]
        AI[AI Agent :8008]
    end

    subgraph T4 ["Tier 4 — Storage & State"]
        PG[(PostgreSQL :5432)]
        RD[(Redis :6379)]
        CH[(ChromaDB :8005)]
    end

    subgraph T5 ["Tier 5 — Presentation"]
        DASH[React Dashboard :3000]
    end

    LS --> US & OS & PS
    OS -->|REST validation| US

    US & OS & PS -->|scrape /metrics| PROM
    US & OS & PS -->|JSON file logs| FB
    FB -->|index api-logs-*| ES
    US & OS & PS -->|OTLP gRPC| JG

    AE -->|query| PROM
    CE -->|search| ES
    AI -->|search| ES
    AI -->|query| PROM
    AI -->|fetch spans| JG
    AI -->|RAG| CH

    AE & RE & CE & IM & AI --> PG
    AE & RE & CE & IM & AI --> RD

    DASH -->|HTTP REST| IM
    DASH -->|direct query| PROM
    RD -.->|WS bridge optional| IM
    IM --> DASH
```

**Design principles:**

- **Async event-driven pipeline** — Redis Pub/Sub decouples detection, rule evaluation, AI analysis, and alerting.
- **Deterministic before AI** — Known failure patterns are handled by the rule engine without LLM cost.
- **Batched AI** — Unknown anomalies are queued for 30 seconds and analyzed in one Groq call per service/metric cluster (not per event).
- **RAG memory** — Resolved incidents are embedded into ChromaDB for similarity retrieval on future incidents.
- **Traffic-gated detection** — Anomaly and clustering engines skip work when the load simulator is not running.

---

## 2. Tier Architecture

### Tier 1 — Monitored Application

Three FastAPI microservices simulate an e-commerce API with realistic failure modes:

| Service | Port | Simulated failures |
|---------|------|-------------------|
| **user-service** | 8001 | 10% DB connection timeouts (~30s), circuit breaker (503 after 10 failures), login failures |
| **order-service** | 8002 | Downstream user validation, order workflow errors |
| **payment-service** | 8003 | 30% gateway timeouts (5–10s), 10% payment declines |

All services share:

- **Structured JSON logging** → `/logs/{service-name}.log` on shared Docker volume
- **Prometheus metrics** at `/metrics` (scraped every 10s)
- **OpenTelemetry tracing** → Jaeger via OTLP gRPC (port 4317)
- **Circuit breaker** pattern on critical dependencies

The **load simulator** (`services/load_simulator.py`) runs on the host and drives traffic to `localhost:8001/8002/8003`:

```mermaid
stateDiagram-v2
    [*] --> NORMAL
    NORMAL --> STORM: every 30s
    STORM --> NORMAL: every 30s

    state NORMAL {
        [*] --> MixedTraffic
        MixedTraffic: 40% user, 40% order, 20% payment
        MixedTraffic: 0.1–0.3s delay between requests
    }

    state STORM {
        [*] --> HeavyLoad
        HeavyLoad: 65% payment (gateway timeouts)
        HeavyLoad: 20% user (DB timeouts)
        HeavyLoad: 15% order (cascading)
        HeavyLoad: 0.02–0.08s delay (15 concurrent workers)
    }
```

### Tier 2 — Observability Infrastructure

| Component | Role |
|-----------|------|
| **Prometheus** | Scrapes `http_requests_total`, `http_request_duration_seconds_bucket`, `db_connection_errors_total`, `payment_gateway_timeouts_total`, `login_failures_total` |
| **Fluent Bit** | Tails `/logs/*.log`, parses JSON, ships to Elasticsearch index `api-logs-*` (5s flush) |
| **Elasticsearch** | Stores searchable log documents with `@timestamp`, `service`, `level`, `message`, `trace_id` |
| **Jaeger** | All-in-one trace backend with OTLP collector |
| **Grafana** | Pre-provisioned datasources for Prometheus and Elasticsearch (admin / admin123) |

### Tier 3 — Operations & AI Engines

| Engine | Schedule | Input | Output |
|--------|----------|-------|--------|
| **Anomaly Engine** | Every 60s | Prometheus metric snapshots | `anomalies` table + Redis `anomaly_events` |
| **Rule Engine** | Event-driven | Redis `anomaly_events` | Redis `rule_matches` or `needs_ai_analysis` |
| **Clustering Engine** | Every 2 min | Elasticsearch ERROR/WARNING logs | `failure_clusters` table + Redis `cluster_updates` |
| **Incident Manager** | Event-driven + REST | Redis `rule_matches`, PostgreSQL | `incidents` table, REST API, optional WebSocket bridge |
| **AI Agent** | 30s batch flush | Redis `needs_ai_analysis` | `incidents` + `ai_analyses` tables, Redis `ai_analysis_completed` |

### Tier 4 — Storage & State

| Store | Purpose |
|-------|---------|
| **PostgreSQL** | Anomalies, failure clusters, incidents, AI analyses |
| **Redis** | Pub/Sub channels, deduplication keys (`anomaly_dedup:*`, `ai_analysis:*`), embedding cache |
| **ChromaDB** | Vector collection `incident_memory` for RAG over resolved incidents |

### Tier 5 — Presentation

React (Vite) dashboard at port **3000**, polling Incident Manager at `127.0.0.1:8013` and Prometheus at `localhost:9090`.

---

## 3. Docker Services Reference

All services are defined in `monitoring-system/docker-compose.yml`.

```mermaid
flowchart LR
    subgraph Infra ["Infrastructure"]
        PG[postgres :5432]
        RD[redis :6379]
        ES[elasticsearch :9200]
        CH[chromadb :8005]
        PROM[prometheus :9090]
        GF[grafana :3001]
        JG[jaeger :16686]
        FB[fluent-bit]
    end

    subgraph Apps ["Application"]
        US[user-service :8001]
        OS[order-service :8002]
        PS[payment-service :8003]
    end

    subgraph Engines ["Operations & AI"]
        AE[anomaly-engine :8004]
        RE[rule-engine :8015]
        CE[clustering-engine :8006]
        IM[incident-manager :8013]
        AI[ai-agent :8008]
    end

    subgraph Init ["Bootstrap"]
        ESI[es-init]
        MLB[ml-base]
    end

    ESI --> ES & PG
    MLB -.->|base image| AE & CE & AI
    US & OS & PS --> FB
    FB --> ES
    US & OS & PS --> PROM
    AE & RE & CE & IM & AI --> PG & RD
```

### Complete service table

| Docker service | Image / Build | Host port | Internal port | Health check | Depends on |
|----------------|---------------|-----------|---------------|--------------|------------|
| `elasticsearch` | elasticsearch:8.13.0 | 9200 | 9200 | cluster health | — |
| `postgres` | postgres:16-alpine | 5432 | 5432 | pg_isready | — |
| `redis` | redis:7-alpine | 6379 | 6379 | redis-cli ping | — |
| `chromadb` | chromadb/chroma:latest | 8005 | 8000 | — | — |
| `prometheus` | prom/prometheus:latest | 9090 | 9090 | — | — |
| `grafana` | grafana/grafana:latest | 3001 | 3000 | — | prometheus, elasticsearch |
| `jaeger` | jaegertracing/all-in-one | 16686, 4317 | — | — | — |
| `fluent-bit` | fluent/fluent-bit:latest | — | — | — | elasticsearch |
| `user-service` | build `./services/user_service` | 8001 | 8001 | — | postgres, redis |
| `order-service` | build `./services/order_service` | 8002 | 8002 | — | user-service |
| `payment-service` | build `./services/payment_service` | 8003 | 8003 | — | postgres, redis |
| `es-init` | python:3.11-slim | — | — | one-shot | postgres, elasticsearch |
| `ml-base` | build `docker/ml-base.Dockerfile` | — | — | one-shot | — |
| `anomaly-engine` | build `./anomaly_engine` | 8004 | 8004 | /health | postgres, redis, prometheus, es-init |
| `rule-engine` | build `./rule_engine` | **8015** | 8005 | /health | redis, prometheus |
| `clustering-engine` | build `./clustering_engine` | 8006 | 8006 | /health | postgres, redis, elasticsearch, es-init |
| `incident-manager` | build `./incident_manager` | **8013** | 8007 | /health | postgres, redis, es-init |
| `ai-agent` | build `./ai_agent` | 8008 | 8008 | /health | postgres, redis, chromadb, elasticsearch, es-init |

### Shared Docker volumes

| Volume | Mounted by | Purpose |
|--------|-----------|---------|
| `logs-volume` | user/order/payment services, fluent-bit, incident-manager | Shared JSON log files at `/logs/{service}.log` |
| `es-data` | elasticsearch | Index persistence |
| `pg-data` | postgres | Database persistence |
| `redis-data` | redis | Redis persistence |
| `chroma-data` | chromadb | Vector store persistence |
| `grafana-data` | grafana | Dashboard state |
| `flb-data` | fluent-bit | Fluent Bit position DB |

### Services not in Docker Compose

| Module | Status |
|--------|--------|
| `alert_system/` | Code exists (Slack/email alerters, deduplicator) but **not deployed** in current compose file |
| `dashboard/` | Run locally via `npm run dev` (port 3000) |

---

## 4. Directory Structure

```
monitoring-system/
├── docker-compose.yml              # All infrastructure and engine services
├── .env.example                    # Environment variable template
├── requirements.txt                # Shared Python dependencies
│
├── init_scripts/
│   ├── create_es_template.py       # Elasticsearch index template for api-logs-*
│   └── create_pg_tables.py         # PostgreSQL DDL (anomalies, clusters, incidents, ai_analyses)
│
├── docker/
│   ├── ml-base.Dockerfile          # Shared ML base (torch, faiss, sentence-transformers, sklearn)
│   ├── ml-base-requirements.txt
│   └── python-service.Dockerfile
│
├── services/                       # Tier 1 — Monitored applications
│   ├── load_simulator.py           # Host-side traffic generator
│   ├── user_service/
│   │   ├── main.py                 # FastAPI app, DB timeout simulation, circuit breaker
│   │   ├── logger.py               # FlushingRotatingFileHandler → /logs/user-service.log
│   │   ├── metrics.py              # Prometheus counters (DB_ERRORS, LOGIN_FAILURES)
│   │   ├── circuit_breaker.py
│   │   └── tracing.py              # OpenTelemetry → Jaeger
│   ├── order_service/
│   └── payment_service/
│
├── collector/                      # Tier 2 — Observability configs
│   ├── prometheus.yml              # Scrape targets: user/order/payment :8001-8003
│   ├── fluent_bit/
│   │   ├── fluent-bit.conf         # Tail /logs/*.log → Elasticsearch
│   │   └── parsers.conf            # JSON parser
│   └── grafana/
│       └── provisioning/           # Datasources + dashboard provisioning
│
├── anomaly_engine/                 # Tier 3 — Metric anomaly detection
│   ├── main.py                     # FastAPI + scheduler lifespan
│   ├── scheduler.py                # 60s detection loop, 24h retrain, 1h cleanup
│   ├── zscore_detector.py          # Rolling Z-Score per metric
│   ├── isolation_forest_detector.py # Multivariate outlier detection
│   ├── prometheus_client.py      # PromQL query helpers
│   └── models.py                   # AnomalyEvent dataclass
│
├── rule_engine/                    # Tier 3 — Deterministic rule matching
│   ├── main.py                     # Redis subscriber + FastAPI
│   ├── engine.py                   # Rule evaluation orchestrator
│   ├── evaluator.py                # Condition logic (AND, CROSS_SERVICE, SINGLE)
│   ├── rules.yaml                  # db_saturation, cascade_failure, circuit_breaker, gateway_degraded
│   └── prometheus_client.py
│
├── clustering_engine/              # Tier 3 — Log failure clustering
│   ├── main.py
│   ├── scheduler.py                # 2-minute clustering loop
│   ├── es_client.py                # Fetch ERROR/WARNING logs from Elasticsearch
│   ├── embedder.py                 # SentenceTransformer + Redis embedding cache
│   ├── clusterer.py                # FAISS + Union-Find (DSU)
│   └── cluster_store.py            # PostgreSQL persistence
│
├── incident_manager/               # Tier 3 — Incident lifecycle + central API
│   ├── main.py                     # FastAPI app, Redis subscriptions, lifecycle scheduler
│   ├── api.py                      # REST endpoints (incidents, logs, clusters, anomalies, prometheus proxy)
│   ├── manager.py                  # handle_rule_match → create RULE_ENGINE incidents
│   ├── lifecycle.py                # 5-min escalation check (WARNING → CRITICAL)
│   ├── ws_hub.py                   # WebSocket routes + Redis-to-WS bridge
│   ├── es_logs.py                  # Elasticsearch log search + file_logs fallback
│   ├── file_logs.py                # Tail-read /logs/*.log when ES is empty/slow
│   ├── auth.py                     # JWT auth (bypassed in dev — returns admin)
│   └── models.py                   # Pydantic response models
│
├── ai_agent/                       # Tier 3 — LLM root-cause analysis
│   ├── main.py                     # FastAPI + Redis subscribers
│   ├── batch_processor.py          # 30s batch queue, dedup cooldown 600s
│   ├── agent.py                    # RootCauseAgent — LLM call + result normalization
│   ├── context_builder.py          # Aggregates logs, metrics, traces, clusters
│   ├── prompt_template.py          # Groq prompt with debug_steps schema
│   ├── incident_memory.py          # ChromaDB RAG store/retrieve
│   ├── llm_factory.py              # Groq / OpenAI-compatible LLM factory
│   ├── confidence_scorer.py
│   └── rate_limiter.py
│
├── alert_system/                   # Not deployed — future Slack/email notifications
│   ├── main.py
│   ├── slack_alerter.py
│   ├── email_alerter.py
│   └── deduplicator.py
│
└── dashboard/                      # Tier 5 — React frontend
    ├── src/
    │   ├── api/client.js           # Axios clients, getLogs fallback, Prometheus queries
    │   ├── pages/
    │   │   ├── Dashboard.jsx       # Main monitoring view
    │   │   ├── IncidentDetail.jsx  # Full incident context + AI RCA
    │   │   └── Login.jsx
    │   ├── components/
    │   │   ├── ServiceHealthGrid.jsx
    │   │   ├── MetricsPanel.jsx
    │   │   ├── AnomalyPanel.jsx
    │   │   ├── IncidentList.jsx
    │   │   ├── ClusterView.jsx
    │   │   ├── LogViewer.jsx
    │   │   ├── RootCauseCard.jsx
    │   │   ├── TraceViewer.jsx
    │   │   └── RelatedErrorLogs.jsx
    │   └── utils/safeRender.js
    ├── .env.development            # VITE_API_URL=http://127.0.0.1:8013
    └── vite.config.js              # Dev server port 3000
```

---

## 5. Telemetry Pipeline

### 5.1 Logs

Microservices write structured JSON via `FlushingRotatingFileHandler` (immediate flush after each log line):

```json
{
  "timestamp": "2026-05-24T14:12:19.456Z",
  "level": "ERROR",
  "levelname": "ERROR",
  "service": "user-service",
  "message": "DB connection timeout after 30s",
  "endpoint": "/users/12345",
  "status_code": 500,
  "latency_ms": 30000.0,
  "trace_id": "8f9a2b7c4d5e6f8a1b2c3d4e5f6a7b8c",
  "span_id": "1a2b3c4d5e6f7a8b"
}
```

```mermaid
flowchart LR
    APP[Microservice] -->|write JSON| FILE["/logs/service-name.log"]
    FILE -->|tail 2s refresh| FB[Fluent Bit]
    FB -->|bulk index| ES["Elasticsearch api-logs-*"]
    ES -->|search| IM[Incident Manager]
    FILE -->|fallback tail-read| IM
    IM -->|GET /logs| DASH[Dashboard LogViewer]
```

**Log retrieval paths:**

1. **Primary:** Incident Manager queries Elasticsearch (`es_logs.py`) with 3s timeout
2. **Fallback:** If ES returns empty or times out, `file_logs.py` tail-reads the last 256 KB of `/logs/{service}.log` from the shared volume

### 5.2 Metrics

Prometheus scrapes each service every 10 seconds:

| Metric | Labels | Used for |
|--------|--------|----------|
| `http_requests_total` | `job`, `status` | Error rate (4xx + 5xx) |
| `http_request_duration_seconds_bucket` | `job`, `le` | p95 latency |
| `db_connection_errors_total` | `service` | DB saturation rules |
| `payment_gateway_timeouts_total` | `service` | Gateway degradation rules |
| `login_failures_total` | `service` | Auth failure tracking |

Example PromQL used by the dashboard:

```promql
# Error rate (4xx + 5xx) per service
(sum(rate(http_requests_total{job="user-service",status=~"5.."}[5m]))
 + sum(rate(http_requests_total{job="user-service",status=~"4.."}[5m])))
/ clamp_min(sum(rate(http_requests_total{job="user-service"}[5m])), 0.001)

# p95 latency
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket{job="user-service"}[5m])) by (le)
) * 1000
```

### 5.3 Traces

OpenTelemetry SDK in each microservice exports spans to Jaeger via OTLP gRPC (`jaeger:4317`). When `order-service` calls `user-service`, W3C `traceparent` headers propagate context so the AI agent can reconstruct call chains.

---

## 6. Operations Event Pipeline

### Full sequence diagram

```mermaid
sequenceDiagram
    autonumber
    actor Sim as Load Simulator
    participant App as Microservices
    participant Prom as Prometheus
    participant ES as Elasticsearch
    participant JG as Jaeger
    participant AE as Anomaly Engine
    participant RD as Redis
    participant PG as PostgreSQL
    participant RE as Rule Engine
    participant IM as Incident Manager
    participant AI as AI Agent
    participant CH as ChromaDB
    participant CE as Clustering Engine
    participant DASH as Dashboard

    Sim->>App: HTTP traffic
    App->>Prom: Expose /metrics
    App->>ES: JSON logs (via Fluent Bit)
    App->>JG: OTLP spans

    Note over AE: Every 60 seconds
    AE->>Prom: Full metric snapshot per service
    AE->>AE: Z-Score + Isolation Forest
    alt Anomaly detected & not deduplicated
        AE->>RD: SET anomaly_dedup:{svc}:{metric} TTL 10m
        AE->>PG: INSERT anomalies
        AE->>RD: PUBLISH anomaly_events
    end

    RD->>RE: anomaly_events
    RE->>Prom: Cross-service metric fetch
    RE->>RE: Evaluate rules.yaml

    alt Rule matches
        RE->>RD: PUBLISH rule_matches
        RD->>IM: rule_matches
        IM->>PG: INSERT incident (source=RULE_ENGINE)
        IM->>RD: PUBLISH incidents_to_alert
    else No rule match
        RE->>RD: PUBLISH needs_ai_analysis
        RD->>AI: needs_ai_analysis → enqueue
        Note over AI: AIBatchProcessor flush every 30s
        AI->>RD: GET ai_analysis:{hash} — skip if cooldown
        AI->>CH: Similar incident RAG query
        AI->>ES: Recent ERROR logs
        AI->>Prom: Current metrics
        AI->>JG: Slowest span, first error, call chain
        AI->>AI: Groq LLM call (one per cluster)
        AI->>PG: INSERT incident (source=AI_AGENT) + ai_analyses
        AI->>RD: PUBLISH ai_analysis_completed, incidents_to_alert
    end

    Note over CE: Every 2 minutes
    CE->>ES: Fetch ERROR/WARNING logs (30 min window)
    CE->>CE: Embed + FAISS cluster
    CE->>PG: UPSERT failure_clusters
    CE->>RD: PUBLISH cluster_updates

    DASH->>IM: Poll /incidents, /anomalies, /clusters, /logs
    DASH->>Prom: Direct metric range queries
```

### Incident sources

| Source | Created by | Has root_cause at creation | AI analysis record |
|--------|-----------|--------------------------|-------------------|
| `RULE_ENGINE` | Incident Manager on `rule_matches` | Yes (from `rules.yaml` diagnosis) | No |
| `AI_AGENT` | AI Agent batch processor | Yes (from LLM) | Yes (`ai_analyses` table) |

---

## 7. Redis Event Bus

```mermaid
flowchart LR
    AE[Anomaly Engine] -->|anomaly_events| RD[(Redis Pub/Sub)]

    RD -->|anomaly_events| RE[Rule Engine]

    RE -->|rule_matches| RD
    RE -->|needs_ai_analysis| RD

    RD -->|rule_matches| IM[Incident Manager]
    RD -->|needs_ai_analysis| AI[AI Agent]

    IM -->|incidents_to_alert| RD
    IM -->|incidents_resolved| RD

    AI -->|incidents_to_alert| RD
    AI -->|ai_analysis_completed| RD

    CE[Clustering Engine] -->|cluster_updates| RD

    RD -->|incidents_resolved| AI
    RD -.->|optional WS bridge| IM
```

### Channel reference

| Channel | Publisher | Subscriber(s) | Payload | Purpose |
|---------|-----------|---------------|---------|---------|
| `anomaly_events` | Anomaly Engine | Rule Engine | `AnomalyEvent` JSON | New metric anomaly detected |
| `rule_matches` | Rule Engine | Incident Manager | Rule match + diagnosis | Deterministic incident creation |
| `needs_ai_analysis` | Rule Engine | AI Agent | Anomaly event | Route unknown anomalies to LLM |
| `incidents_to_alert` | Incident Manager, AI Agent | Dashboard WS bridge | Incident JSON | Notify UI of new incidents |
| `ai_analysis_completed` | AI Agent | Dashboard WS bridge | Analysis JSON | Notify UI that RCA is ready |
| `incidents_resolved` | Incident Manager | AI Agent | Resolved incident | Store resolution in ChromaDB RAG |
| `cluster_updates` | Clustering Engine | *(future)* | Cluster JSON | New/updated failure cluster |

### Deduplication keys

| Key pattern | TTL | Set by | Purpose |
|-------------|-----|--------|---------|
| `anomaly_dedup:{service}:{metric}` | 10 min | Anomaly Engine | Prevent duplicate anomaly events |
| `ai_analysis:{cluster_hash}` | 600s (10 min) | AI Agent | Prevent duplicate LLM calls for same cluster |

---

## 8. Component Deep Dives

### 8.1 Anomaly Engine

**Schedule:** detection every 60s, model retrain every 24h, cleanup every 1h.

**Per-service metric snapshot** (from Prometheus):

- `error_rate` — 5xx rate / total request rate
- `p95_latency_ms` — histogram quantile × 1000
- `request_volume` — requests per second
- `db_errors` — rate of `db_connection_errors_total`
- `gateway_timeouts` — rate of `payment_gateway_timeouts_total`

**Detectors run in parallel:**

1. **ZScoreDetector** — per-metric rolling window (`deque(maxlen=30)`)
2. **IsolationForestDetector** — multivariate over all 5 metrics

On detection: dedup check → PostgreSQL insert → Redis publish.

### 8.2 Rule Engine

Subscribes to `anomaly_events`. For each event:

1. Fetch full metric snapshots for all three services
2. Evaluate conditions in `rules.yaml`
3. If match → publish `rule_matches` with diagnosis, recommendation, confidence, severity
4. If no match → publish `needs_ai_analysis`

**Defined rules:**

| Rule | Logic | Trigger |
|------|-------|---------|
| `db_saturation` | AND | `db_errors > 0.5` AND `p95_latency_ms > 2000` |
| `cascade_failure` | CROSS_SERVICE | user error_rate > 0.3 AND order error_rate > 0.2 |
| `circuit_breaker_open` | SINGLE | status_code == 503 |
| `payment_gateway_degraded` | SINGLE | gateway_timeouts > 0.3 |

### 8.3 AI Agent

**Batch processor** (`AIBatchProcessor`):

```mermaid
flowchart TD
    E[needs_ai_analysis event] --> Q[In-memory queue]
    Q -->|every 30s| F[Flush]
    F --> G[Group by service:metric]
    G --> H{Cooldown key exists?}
    H -->|yes| SKIP[Skip cluster]
    H -->|no| CTX[Build context]
    CTX --> RAG[ChromaDB similar incidents]
    CTX --> LOGS[Elasticsearch error logs]
    CTX --> MET[Prometheus metrics]
    CTX --> TR[Jager trace summary]
    CTX --> LLM[Groq LLM call]
    LLM --> PG[(incidents + ai_analyses)]
    LLM --> PUB[Publish ai_analysis_completed]
```

**LLM output schema** (stored in `ai_analyses.raw_response` JSONB):

```json
{
  "root_cause": "one sentence probable root cause",
  "severity": "WARNING | CRITICAL",
  "confidence": 0.85,
  "affected_services": ["payment-service"],
  "recommended_actions": ["action1", "action2"],
  "summary": "2-3 sentence summary with evidence",
  "evidence": ["metric spike", "error log sample"],
  "debug_steps": ["Search ES logs", "Check Jaeger traces", "Query Prometheus"]
}
```

**Fallback debug steps** are injected server-side when the LLM omits them or for legacy records.

**RAG on resolve:** When an operator resolves an incident, Incident Manager publishes to `incidents_resolved`. AI Agent embeds title + root cause + resolution notes into ChromaDB `incident_memory`.

### 8.4 Clustering Engine

**Schedule:** every 2 minutes (immediate run on startup).

1. Query Elasticsearch for ERROR and WARNING logs in the last 30 minutes
2. Embed log messages with `SentenceTransformer("all-MiniLM-L6-v2")` → 384-dim vectors
3. Build FAISS `IndexFlatIP` (inner product = cosine similarity on normalized vectors)
4. Union-Find (DSU) merges logs with similarity ≥ 0.85
5. Elect centroid message as cluster representative
6. Upsert to `failure_clusters` table
7. Publish `cluster_updates` to Redis

**Dashboard fallback:** If `failure_clusters` is empty, Incident Manager `/clusters` returns open incidents as pseudo-clusters.

### 8.5 Incident Manager

Central API gateway and incident lifecycle coordinator.

**Redis subscriptions:**

- `rule_matches` → `manager.handle_rule_match()` → create RULE_ENGINE incident

**Lifecycle scheduler** (every 5 min):

- Escalate WARNING → CRITICAL if cluster member count grows > 1.5× since incident creation

**Log API strategy:**

- Elasticsearch search with 4s asyncio timeout
- File log fallback from shared volume
- Per-service endpoint: `GET /services/{name}/logs`

**Dev hot-reload:** Source mounted at `./incident_manager:/app` — restart container to pick up changes without rebuild.

---

## 9. Algorithms & Detection Logic

### 9.1 Rolling Z-Score

For each service metric, maintain a rolling window of 30 snapshots:

$$\mu = \text{mean}(\text{window}), \quad \sigma = \text{std\_dev}(\text{window})$$

$$Z = \frac{x - \mu}{\max(\sigma, \epsilon)}$$

| Condition | Severity |
|-----------|----------|
| Z > 3 | CRITICAL |
| Z > 2 | WARNING |

### 9.2 Isolation Forest

- **Training:** Every 24h, fetch 7 days of 5-minute metric snapshots per service
- **Model:** `sklearn.ensemble.IsolationForest(contamination=0.05)`
- **Prediction:** decision score ≤ −0.2 → CRITICAL; otherwise WARNING

### 9.3 FAISS Log Clustering

```
1. Fetch N error logs from ES
2. V = SentenceTransformer.encode(messages)  →  R^(N×384)
3. Normalize V; build faiss.IndexFlatIP(384)
4. For each pair (i,j): if cos_sim(V[i], V[j]) ≥ 0.85 → union(i,j)
5. For each component: representative = argmin distance to centroid
6. Persist cluster with member_count, affected_services, first_seen, last_seen
```

### 9.4 RAG Retrieval

```
1. Embed incident title → query vector q
2. ChromaDB query incident_memory, top-k=5
3. Keep results with cosine similarity > 0.70 (distance < 0.30)
4. Inject similar incidents into LLM prompt as historical context
```

### 9.5 Error Rate Calculation (Dashboard)

Service health error rate is the **maximum** of:

1. Prometheus 4xx + 5xx rate
2. `error_rate_estimate` from incident stats API
3. Minimum 5% floor when critical incidents exist for the service

---

## 10. Database Schemas

Initialized by `init_scripts/create_pg_tables.py` on first `docker compose up`.

### anomalies

```sql
CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(100) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    current_value FLOAT NOT NULL,
    mean FLOAT NOT NULL,
    std FLOAT NOT NULL,
    z_score FLOAT,
    anomaly_score FLOAT,
    severity VARCHAR(20) NOT NULL,       -- WARNING, CRITICAL
    detector VARCHAR(50) NOT NULL,       -- zscore, isolation_forest
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### failure_clusters

```sql
CREATE TABLE failure_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    representative_message TEXT NOT NULL,
    member_count INTEGER NOT NULL DEFAULT 1,
    affected_services TEXT[] NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### incidents

```sql
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',  -- OPEN, ACKNOWLEDGED, RESOLVED
    severity VARCHAR(20) NOT NULL,                -- WARNING, CRITICAL
    affected_services TEXT[] NOT NULL,
    cluster_id UUID REFERENCES failure_clusters(id),
    root_cause TEXT,
    confidence FLOAT,
    source VARCHAR(20) NOT NULL,                  -- RULE_ENGINE, AI_AGENT
    similar_incident_ids UUID[],
    alert_sent BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);
```

### ai_analyses

```sql
CREATE TABLE ai_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id),
    root_cause TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    affected_services TEXT[] NOT NULL DEFAULT '{}',
    recommended_actions TEXT[] NOT NULL DEFAULT '{}',
    summary TEXT,
    raw_response JSONB,                           -- full LLM JSON incl. debug_steps, evidence
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Stats API shape (`GET /incidents/stats/summary`)

```json
{
  "total_open": 9,
  "total_critical": 2,
  "by_service": {
    "payment-service": {
      "open": 4,
      "critical": 1,
      "error_rate_estimate": 0.225
    }
  },
  "by_status": { "OPEN": 8, "ACKNOWLEDGED": 1, "RESOLVED": 1 }
}
```

---

## 11. Incident Manager API

Base URL: `http://127.0.0.1:8013` (host) / `http://incident-manager:8007` (Docker network)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| GET | `/incidents` | List incidents (filters: status, severity, service, limit) |
| GET | `/incidents/{id}` | Full incident detail + AI analysis + logs + metrics + traces |
| PATCH | `/incidents/{id}` | Update status (ACKNOWLEDGED, RESOLVED), resolution_notes |
| GET | `/incidents/stats/summary` | Open/critical counts per service |
| GET | `/anomalies` | Recent anomaly events |
| GET | `/clusters` | Failure clusters (fallback to open incidents if empty) |
| GET | `/logs` | All-service log search (ES + file fallback) |
| GET | `/logs/service/{name}` | Service-specific logs |
| GET | `/services/{name}/logs` | Service-specific logs (preferred by dashboard) |
| GET | `/prometheus/api/v1/query` | Prometheus instant query proxy |
| GET | `/prometheus/api/v1/query_range` | Prometheus range query proxy |
| WS | `/ws/logs` | Live log stream (optional; dashboard uses HTTP poll) |
| WS | `/ws/anomalies` | Anomaly event stream |
| WS | `/ws/incidents` | Incident event stream |

---

## 12. Dashboard Architecture

```mermaid
flowchart TB
    subgraph Pages
        DASH[Dashboard.jsx]
        ID[IncidentDetail.jsx]
        LOGIN[Login.jsx]
    end

    subgraph Components
        SHG[ServiceHealthGrid]
        MP[MetricsPanel]
        AP[AnomalyPanel]
        IL[IncidentList]
        CV[ClusterView]
        LV[LogViewer]
        RCC[RootCauseCard]
        TV[TraceViewer]
        REL[RelatedErrorLogs]
    end

    subgraph APIs
        IM[Incident Manager :8013]
        PROM[Prometheus :9090]
    end

    DASH --> SHG & MP & AP & IL & CV & LV
    ID --> RCC & TV & REL & MP

    SHG --> IM & PROM
    MP --> PROM
    AP & IL & CV & LV --> IM
    ID --> IM
```

### Polling intervals

| Component | Interval | Endpoint |
|-----------|----------|----------|
| ServiceHealthGrid | 45s | `/incidents/stats/summary` + Prometheus instant |
| MetricsPanel | 30s | Prometheus range (last 30 min) |
| AnomalyPanel | 60s | `/anomalies` |
| IncidentList | 45s | `/incidents` |
| ClusterView | 60s | `/clusters?status=open` |
| LogViewer | 5s | `/logs` or `/services/{svc}/logs` |

### Key implementation notes

- **Windows IPv6 fix:** `VITE_API_URL=http://127.0.0.1:8013` (not `localhost`)
- **HTTP polling over WebSocket:** Dashboard uses HTTP polling for reliability; WebSocket connections were removed from AnomalyPanel and IncidentList to prevent connection exhaustion
- **getLogs fallback:** On timeout/404, fetches per-service logs in parallel and merges
- **safeRender.js:** Coerces API values to safe React children; handles legacy `by_service` number format

---

## 13. Environment Configuration

Copy `monitoring-system/.env.example` → `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_URL` | `postgresql+asyncpg://monitor:monitor123@postgres:5432/monitoring` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379` | Redis connection |
| `ES_URL` | `http://elasticsearch:9200` | Elasticsearch |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus |
| `JAEGER_URL` | `http://jaeger:16686` | Jaeger UI/API |
| `CHROMA_HOST` | `chromadb` | ChromaDB hostname |
| `CHROMA_PORT` | `8000` | ChromaDB internal port |
| `LLM_PROVIDER` | `groq` | LLM provider |
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `JWT_SECRET` | *(change in prod)* | JWT signing secret |
| `AI_BATCH_INTERVAL_SEC` | `30` | AI batch flush interval |
| `AI_COOLDOWN_TTL_SEC` | `600` | AI dedup cooldown |

**Load simulator env vars** (host-side):

| Variable | Default |
|----------|---------|
| `USER_SERVICE_URL` | `http://localhost:8001` |
| `ORDER_SERVICE_URL` | `http://localhost:8002` |
| `PAYMENT_SERVICE_URL` | `http://localhost:8003` |

---

## 14. Zero-Traffic Filtering

When the load simulator is **not running**, request rate drops below 0.1 req/s. The system suppresses false positives:

```mermaid
flowchart TD
    PROM[Prometheus] -->|rate query| CHECK{rate > 0.1/s?}
    CHECK -->|no| SKIP[Skip detection]
    CHECK -->|yes| RUN[Run detectors]

    SKIP --> AE[Anomaly Engine: skip 60s loop]
    SKIP --> CE[Clustering Engine: skip 2min loop]
```

**PromQL traffic check:**

```promql
sum(rate(http_requests_total{
  job=~"(user-service|order-service|payment-service)",
  handler!="/metrics"
}[1m]))
```

**Incident Manager behavior when traffic is inactive:** API may return empty sets for `/incidents`, `/clusters`, `/anomalies` to present a clean dashboard state.

---

## 15. Deployment & Development Notes

### Build order

```powershell
cd monitoring-system
$env:DOCKER_BUILDKIT = "1"
docker compose build ml-base      # Once — caches ML dependencies
docker compose up -d --build      # All services
```

### Run locally (not in Docker)

| Component | Command | Port |
|-----------|---------|------|
| Load simulator | `python services/load_simulator.py` | — |
| Dashboard | `cd dashboard && npm run dev` | 3000 |

### Development workflow

| Change location | Action |
|----------------|--------|
| `incident_manager/` | Volume-mounted — `docker compose restart incident-manager` |
| Other engine source | Rebuild: `docker compose up -d --build <service>` |
| Dashboard | Hot reload via Vite (restart if `.env.development` changes) |

### Known constraints

- **Docker build network:** `pip install` may fail inside Docker on some networks — use volume mounts for rapid iteration on `incident-manager`
- **Single uvicorn worker:** Incident Manager runs 1 worker to avoid Windows connection exhaustion with many dashboard pollers
- **alert_system:** Implemented but not wired into `docker-compose.yml` — future Slack/email integration

### Health verification commands

```powershell
curl.exe http://127.0.0.1:8013/health
curl.exe http://127.0.0.1:8004/health    # anomaly-engine
curl.exe http://127.0.0.1:8015/health    # rule-engine
curl.exe http://127.0.0.1:8006/health    # clustering-engine
curl.exe http://127.0.0.1:8008/health    # ai-agent
docker compose ps
```

---

## Related Documentation

- **[README.md](./README.md)** — Quick start, port reference, troubleshooting, and high-level overview.
