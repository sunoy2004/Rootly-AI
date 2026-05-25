#!/usr/bin/env python3
"""Clear all monitoring telemetry for a fresh demo (DB, logs, ES, Prometheus, Redis)."""

import asyncio
import os
import subprocess
import sys

import httpx

PG_DSN = os.getenv(
    "POSTGRES_URL",
    "postgresql://monitor:monitor123@localhost:5432/monitoring",
).replace("postgresql+asyncpg://", "postgresql://")

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
COMPOSE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_compose(*args: str) -> bool:
    cmd = ["docker", "compose", *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=COMPOSE_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  warning: {' '.join(cmd)} -> {result.stderr.strip()[:200]}")
            return False
        return True
    except Exception as exc:
        print(f"  warning: docker compose failed ({exc})")
        return False


async def clear_postgres():
    import asyncpg

    conn = await asyncpg.connect(PG_DSN)
    await conn.execute(
        """
        TRUNCATE TABLE
            ai_analyses,
            incidents,
            failure_clusters,
            anomalies
        RESTART IDENTITY CASCADE
        """
    )
    await conn.close()
    print("PostgreSQL: truncated incidents, anomalies, clusters, ai_analyses")


async def clear_elasticsearch():
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{ES_URL}/_cat/indices/api-logs-*?h=index")
            if resp.status_code != 200:
                print("Elasticsearch: no api-logs indices found")
                return
            indices = [line.strip() for line in resp.text.splitlines() if line.strip()]
            for index in indices:
                del_resp = await client.delete(f"{ES_URL}/{index}")
                if del_resp.status_code not in (200, 404):
                    print(f"  failed to delete {index}: {del_resp.status_code}")
            print(f"Elasticsearch: deleted {len(indices)} api-logs index(es)")
        except Exception as exc:
            print(f"Elasticsearch: skip ({exc})")


def clear_log_files():
    """Truncate JSON log files on the shared Docker volume."""
    files = [
        "/logs/user-service.log",
        "/logs/order-service.log",
        "/logs/payment-service.log",
    ]
    ok = True
    for path in files:
        if not run_compose("exec", "-T", "user-service", "truncate", "-s", "0", path):
            ok = False
    if ok:
        print("Log files: truncated user/order/payment logs on shared volume")
    else:
        print("Log files: partial truncate (is user-service running?)")


def reset_prometheus():
    """Recreate Prometheus container to wipe TSDB (no named volume — fresh metrics)."""
    if run_compose("up", "-d", "--force-recreate", "prometheus"):
        print("Prometheus: recreated — old metric time series cleared")
    else:
        print("Prometheus: recreate skipped")


def reset_fluent_bit():
    """Restart Fluent Bit so it re-tails from the start of empty log files."""
    if run_compose("restart", "fluent-bit"):
        print("Fluent Bit: restarted")


async def clear_redis_dedup():
    try:
        import redis.asyncio as aioredis

        r = await aioredis.from_url(REDIS_URL)
        keys = []
        async for key in r.scan_iter("anomaly_dedup:*"):
            keys.append(key)
        async for key in r.scan_iter("ai_analysis:*"):
            keys.append(key)
        if keys:
            await r.delete(*keys)
        await r.close()
        print(f"Redis: cleared {len(keys)} dedup keys")
    except Exception as exc:
        print(f"Redis: skip ({exc})")


async def main():
    print("=== Rootly-AI full telemetry reset ===\n")
    await clear_postgres()
    await clear_elasticsearch()
    clear_log_files()
    reset_prometheus()
    reset_fluent_bit()
    await clear_redis_dedup()
    print("\nDone.")
    print("Next: start load simulator, wait ~30s, hard-refresh dashboard (Ctrl+Shift+R).")


if __name__ == "__main__":
    asyncio.run(main())
