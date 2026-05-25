import asyncio
import os
import random
import time
from uuid import uuid4

import httpx

USER_BASE = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
ORDER_BASE = os.getenv("ORDER_SERVICE_URL", "http://localhost:8002")
PAYMENT_BASE = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003")

# Mostly healthy traffic; short stress bursts for anomalies/incidents
NORMAL_SECONDS = int(os.getenv("SIM_NORMAL_SECONDS", "180"))
STORM_SECONDS = int(os.getenv("SIM_STORM_SECONDS", "45"))
CONCURRENCY = int(os.getenv("SIM_CONCURRENCY", "6"))

USER_IDS = [str(uuid4()) for _ in range(10)]
KNOWN_ORDER_IDS: list[str] = []
MODE = "NORMAL"


async def send_request(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    start = time.time()
    try:
        response = await client.request(method, url, **kwargs)
        latency_ms = (time.time() - start) * 1000
        if response.status_code >= 400 or random.random() < 0.03:
            print(f"{method} {url} -> {response.status_code} ({latency_ms:.0f}ms) [{MODE}]")
        return response
    except Exception as exc:
        latency_ms = (time.time() - start) * 1000
        print(f"{method} {url} -> ERROR {type(exc).__name__} ({latency_ms:.0f}ms) [{MODE}]")
        return None


async def random_user_request(client: httpx.AsyncClient, stress: bool = False):
    roll = random.random()
    if roll < 0.65 or not stress:
        user_id = random.choice(USER_IDS)
        await send_request(client, "GET", f"{USER_BASE}/users/{user_id}")
    else:
        await send_request(
            client,
            "POST",
            f"{USER_BASE}/users/login",
            json={"username": "testuser", "password": "testpass"},
        )


async def random_order_request(client: httpx.AsyncClient, stress: bool = False):
    roll = random.random()
    if roll < 0.55 or not KNOWN_ORDER_IDS:
        resp = await send_request(
            client,
            "POST",
            f"{ORDER_BASE}/orders",
            json={
                "user_id": random.choice(USER_IDS),
                "items": ["item1", "item2"],
                "total": round(random.uniform(10, 500), 2),
            },
        )
        if resp and resp.status_code in (200, 201):
            try:
                oid = resp.json().get("order_id")
                if oid and oid not in KNOWN_ORDER_IDS:
                    KNOWN_ORDER_IDS.append(oid)
                    if len(KNOWN_ORDER_IDS) > 50:
                        KNOWN_ORDER_IDS.pop(0)
            except Exception:
                pass
    else:
        order_id = random.choice(KNOWN_ORDER_IDS)
        await send_request(client, "GET", f"{ORDER_BASE}/orders/{order_id}")


async def random_payment_request(client: httpx.AsyncClient):
    order_id = random.choice(KNOWN_ORDER_IDS) if KNOWN_ORDER_IDS else str(uuid4())
    await send_request(
        client,
        "POST",
        f"{PAYMENT_BASE}/payments",
        json={
            "order_id": order_id,
            "amount": round(random.uniform(10, 500), 2),
            "currency": "USD",
        },
    )


async def mixed_request(client: httpx.AsyncClient, stress: bool = False):
    roll = random.random()
    if roll < 0.35:
        await random_user_request(client, stress=stress)
    elif roll < 0.70:
        await random_order_request(client, stress=stress)
    else:
        await random_payment_request(client)


async def worker_loop(client: httpx.AsyncClient):
    while True:
        try:
            stress = MODE == "STORM"
            await mixed_request(client, stress=stress)
            if stress:
                await asyncio.sleep(random.uniform(0.08, 0.2))
            else:
                await asyncio.sleep(random.uniform(0.25, 0.6))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"Worker error: {exc}")
            await asyncio.sleep(1.0)


async def mode_toggle_loop():
    global MODE
    while True:
        await asyncio.sleep(NORMAL_SECONDS if MODE == "NORMAL" else STORM_SECONDS)
        if MODE == "NORMAL":
            MODE = "STORM"
            print(f"=== STORM MODE ({STORM_SECONDS}s) — elevated error rate ===")
        else:
            MODE = "NORMAL"
            print(f"=== NORMAL MODE ({NORMAL_SECONDS}s) — mostly 200 OK ===")


async def seed_orders(client: httpx.AsyncClient):
    """Create a few orders up front so GET /orders/{id} returns 200."""
    for _ in range(5):
        await random_order_request(client, stress=False)
        await asyncio.sleep(0.2)


async def main():
    print("Rootly-AI Load Simulator")
    print(f"  User:    {USER_BASE}")
    print(f"  Order:   {ORDER_BASE}")
    print(f"  Payment: {PAYMENT_BASE}")
    print(f"  Mode:    {NORMAL_SECONDS}s normal / {STORM_SECONDS}s storm, {CONCURRENCY} workers")
    print()

    limits = httpx.Limits(max_keepalive_connections=30, max_connections=80)
    async with httpx.AsyncClient(limits=limits, timeout=15.0) as client:
        await seed_orders(client)
        asyncio.create_task(mode_toggle_loop())
        workers = [asyncio.create_task(worker_loop(client)) for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Simulator stopped.")
