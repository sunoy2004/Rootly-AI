import asyncio
import os
import random
import time
from uuid import uuid4

import httpx

# Use localhost when running on host; Docker service names when inside compose network
USER_BASE = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
ORDER_BASE = os.getenv("ORDER_SERVICE_URL", "http://localhost:8002")
PAYMENT_BASE = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003")

USER_IDS = [str(uuid4()) for _ in range(20)]
ORDER_IDS = [str(uuid4()) for _ in range(20)]

MODE = "NORMAL"  # Can be "NORMAL" or "STORM"
CONCURRENCY = 15


async def send_request(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    start = time.time()
    try:
        response = await client.request(method, url, **kwargs)
        latency_ms = (time.time() - start) * 1000
        # Only print a sample of successful requests to avoid console flooding
        if response.status_code >= 400 or random.random() < 0.05:
            print(f"{method} {url} -> {response.status_code} ({latency_ms:.1f}ms) [{MODE}]")
    except Exception as exc:
        latency_ms = (time.time() - start) * 1000
        print(f"{method} {url} -> ERROR {type(exc).__name__} ({latency_ms:.1f}ms) [{MODE}]")


async def random_user_request(client: httpx.AsyncClient):
    roll = random.random()
    if roll < 0.50:
        user_id = random.choice(USER_IDS)
        await send_request(client, "GET", f"{USER_BASE}/users/{user_id}")
    else:
        await send_request(
            client,
            "POST",
            f"{USER_BASE}/users/login",
            json={"username": "testuser", "password": "testpass"},
        )


async def random_order_request(client: httpx.AsyncClient):
    roll = random.random()
    if roll < 0.60:
        await send_request(
            client,
            "POST",
            f"{ORDER_BASE}/orders",
            json={
                "user_id": random.choice(USER_IDS),
                "items": ["item1", "item2"],
                "total": round(random.uniform(10, 500), 2),
            },
        )
    else:
        order_id = random.choice(ORDER_IDS)
        await send_request(client, "GET", f"{ORDER_BASE}/orders/{order_id}")


async def random_payment_request(client: httpx.AsyncClient):
    await send_request(
        client,
        "POST",
        f"{PAYMENT_BASE}/payments",
        json={
            "order_id": random.choice(ORDER_IDS),
            "amount": round(random.uniform(10, 500), 2),
            "currency": "USD",
        },
    )


async def worker_loop(client: httpx.AsyncClient):
    """Continuous async request worker loop."""
    while True:
        try:
            if MODE == "NORMAL":
                roll = random.random()
                if roll < 0.40:
                    await random_user_request(client)
                elif roll < 0.80:
                    await random_order_request(client)
                else:
                    await random_payment_request(client)
                # Small random delay under normal mode
                await asyncio.sleep(random.uniform(0.1, 0.3))
            else:
                # STORM MODE: Heavy gateway timeouts, db timeouts, circuit breaker trips
                roll = random.random()
                if roll < 0.65:
                    # Gateway timeouts (payment service timeout = 30%)
                    await random_payment_request(client)
                elif roll < 0.85:
                    # User service timeout (user service timeout = 10%)
                    user_id = random.choice(USER_IDS)
                    await send_request(client, "GET", f"{USER_BASE}/users/{user_id}")
                else:
                    # Cascading failures to order service
                    await random_order_request(client)
                # Ultra fast delay to flood systems and trip breaker
                await asyncio.sleep(random.uniform(0.02, 0.08))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"Worker encounter error: {exc}")
            await asyncio.sleep(0.5)


async def mode_toggle_loop():
    """Toggle simulator mode between Normal and Storm every 30s."""
    global MODE
    while True:
        await asyncio.sleep(30)
        if MODE == "NORMAL":
            MODE = "STORM"
            print("=== MODE SWITCH: STORM MODE ACTIVATED ===")
        else:
            MODE = "NORMAL"
            print("=== MODE SWITCH: NORMAL MODE ACTIVATED ===")


async def main():
    print("Starting Upgraded Load Simulator...")
    print(f"Targets:\n  User: {USER_BASE}\n  Order: {ORDER_BASE}\n  Payment: {PAYMENT_BASE}\n")
    
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=200)
    async with httpx.AsyncClient(limits=limits, timeout=35.0) as client:
        # Start mode toggle task
        asyncio.create_task(mode_toggle_loop())
        
        # Start async request workers
        workers = [asyncio.create_task(worker_loop(client)) for _ in range(CONCURRENCY)]
        
        # Wait forever
        await asyncio.gather(*workers)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Simulator stopped.")
