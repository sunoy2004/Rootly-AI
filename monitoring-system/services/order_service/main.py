import asyncio
import random
import time
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from tracing import init_tracing
from logger import setup_logger
from metrics import UPSTREAM_FAILURES, ORDER_LATENCY

init_tracing("order-service")
logger = setup_logger("order-service")

app = FastAPI(title="Order Service")
Instrumentator().instrument(app).expose(app)

httpx_client = httpx.AsyncClient(timeout=2.0)


class OrderRequest(BaseModel):
    user_id: str
    items: list
    total: float


@app.get("/orders/health")
async def health():
    return {"status": "ok", "service": "order-service"}


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    if random.random() < 0.30:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order_id": order_id, "status": "pending"}


@app.post("/orders")
async def create_order(request: OrderRequest):
    start = time.time()

    try:
        response = await httpx_client.get(
            f"http://user-service:8001/users/{request.user_id}"
        )
        if response.status_code >= 500:
            raise httpx.HTTPStatusError(
                "Upstream error", request=response.request, response=response
            )
    except (httpx.TimeoutException, httpx.HTTPStatusError):
        elapsed = (time.time() - start) * 1000
        UPSTREAM_FAILURES.labels(
            service="order-service", upstream="user-service"
        ).inc()
        ORDER_LATENCY.labels(service="order-service").observe(time.time() - start)
        logger.error(
            "Upstream user validation failed",
            extra={
                "status_code": 502,
                "latency_ms": elapsed,
                "endpoint": "/orders",
            },
        )
        raise HTTPException(status_code=502, detail="Upstream user validation failed")

    await asyncio.sleep(random.uniform(0.1, 0.5))
    elapsed = (time.time() - start) * 1000
    ORDER_LATENCY.labels(service="order-service").observe(time.time() - start)
    logger.info(
        "Order created",
        extra={"status_code": 201, "latency_ms": elapsed},
    )
    return {"order_id": str(uuid4()), "status": "created"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
