import asyncio
import random
import time
from uuid import uuid4

import httpx

USER_BASE = "http://user-service:8001"
ORDER_BASE = "http://order-service:8002"
PAYMENT_BASE = "http://payment-service:8003"

USER_IDS = [str(uuid4()) for _ in range(10)]
ORDER_IDS = [str(uuid4()) for _ in range(10)]


async def send_request(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    start = time.time()
    try:
        response = await client.request(method, url, **kwargs)
        latency_ms = (time.time() - start) * 1000
        print(f"{method} {url} -> {response.status_code} ({latency_ms:.1f}ms)")
    except Exception as exc:
        latency_ms = (time.time() - start) * 1000
        print(f"{method} {url} -> ERROR {type(exc).__name__} ({latency_ms:.1f}ms)")


async def random_user_request(client: httpx.AsyncClient):
    roll = random.random()
    if roll < 0.5:
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
    if roll < 0.5:
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


async def normal_phase(client: httpx.AsyncClient, duration_seconds: int = 480):
    end_time = time.time() + duration_seconds
    while time.time() < end_time:
        count = random.randint(1, 2)
        tasks = []
        for _ in range(count):
            roll = random.random()
            if roll < 0.40:
                tasks.append(random_user_request(client))
            elif roll < 0.70:
                tasks.append(random_order_request(client))
            else:
                tasks.append(random_payment_request(client))
        await asyncio.gather(*tasks)
        await asyncio.sleep(1)


async def storm_phase(client: httpx.AsyncClient, duration_seconds: int = 120):
    print("=== STORM STARTING ===")
    end_time = time.time() + duration_seconds
    while time.time() < end_time:
        count = random.randint(4, 5)
        tasks = []
        for _ in range(count):
            roll = random.random()
            if roll < 0.80:
                tasks.append(random_payment_request(client))
            else:
                user_id = random.choice(USER_IDS)
                tasks.append(
                    send_request(client, "GET", f"{USER_BASE}/users/{user_id}")
                )
        await asyncio.gather(*tasks)
        await asyncio.sleep(1)
    print("=== STORM ENDING ===")


async def main():
    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            await normal_phase(client, duration_seconds=480)
            await storm_phase(client, duration_seconds=120)


if __name__ == "__main__":
    asyncio.run(main())
