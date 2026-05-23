import random
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from tracing import init_tracing
from logger import setup_logger
from metrics import GATEWAY_TIMEOUTS, PAYMENT_DECLINES, GATEWAY_RESPONSE_TIME
from circuit_breaker import CircuitBreaker, CircuitOpenError

init_tracing("payment-service")
logger = setup_logger("payment-service")

app = FastAPI(title="Payment Service")
Instrumentator().instrument(app).expose(app)

circuit_breaker = CircuitBreaker(
    "payment-gateway", failure_threshold=5, recovery_timeout=30
)


class GatewayTimeoutError(Exception):
    pass


class PaymentRequest(BaseModel):
    order_id: str
    amount: float
    currency: str


@app.get("/payments/health")
async def health():
    return {
        "status": "ok",
        "service": "payment-service",
        "circuit_state": circuit_breaker.get_state(),
    }


@app.post("/payments")
async def create_payment(request: PaymentRequest):
    start = time.time()

    async def simulate_gateway():
        roll = random.random()

        if roll < 0.30:
            import asyncio
            await asyncio.sleep(random.uniform(5, 10))
            GATEWAY_TIMEOUTS.labels(service="payment-service").inc()
            GATEWAY_RESPONSE_TIME.labels(service="payment-service").observe(
                time.time() - start
            )
            raise GatewayTimeoutError()

        if roll < 0.40:
            PAYMENT_DECLINES.labels(service="payment-service").inc()
            GATEWAY_RESPONSE_TIME.labels(service="payment-service").observe(
                time.time() - start
            )
            raise HTTPException(status_code=402, detail="Payment declined")

        import asyncio
        await asyncio.sleep(random.uniform(0.1, 0.3))
        GATEWAY_RESPONSE_TIME.labels(service="payment-service").observe(
            time.time() - start
        )
        return {"payment_id": str(uuid4()), "status": "success"}

    try:
        return await circuit_breaker.call(simulate_gateway)
    except CircuitOpenError:
        logger.error(
            "Circuit open: gateway unavailable",
            extra={"status_code": 503},
        )
        raise HTTPException(status_code=503, detail="Circuit open: gateway unavailable")
    except GatewayTimeoutError:
        logger.error(
            "Payment gateway timeout",
            extra={
                "status_code": 504,
                "latency_ms": (time.time() - start) * 1000,
            },
        )
        raise HTTPException(status_code=504, detail="Gateway timeout")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
