import asyncio
import random
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from tracing import init_tracing
from logger import setup_logger
from metrics import DB_ERRORS, ACTIVE_DB_CONNECTIONS, LOGIN_FAILURES
from circuit_breaker import CircuitBreaker, CircuitOpenError

init_tracing("user-service")
logger = setup_logger("user-service")

app = FastAPI(title="User Service")
Instrumentator().instrument(app).expose(app)

circuit_breaker = CircuitBreaker("user-db", failure_threshold=10, recovery_timeout=30)


class DBTimeoutError(Exception):
    pass


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/users/health")
async def health():
    return {
        "status": "ok",
        "service": "user-service",
        "circuit_state": circuit_breaker.get_state(),
    }


@app.get("/users/{user_id}")
async def get_user(user_id: str):
    ACTIVE_DB_CONNECTIONS.labels(service="user-service").set(random.randint(0, 100))

    async def simulate_db():
        if random.random() < 0.03:
            await asyncio.sleep(random.uniform(28, 32))
            DB_ERRORS.labels(service="user-service").inc()
            logger.error(
                "DB connection timeout after 30s",
                extra={
                    "endpoint": f"/users/{user_id}",
                    "status_code": 500,
                    "latency_ms": 30000,
                },
            )
            raise DBTimeoutError("DB connection timeout")
        else:
            start = time.time()
            await asyncio.sleep(random.uniform(0.05, 0.2))
            latency_ms = (time.time() - start) * 1000
            logger.info(
                "User fetched",
                extra={
                    "endpoint": f"/users/{user_id}",
                    "status_code": 200,
                    "latency_ms": latency_ms,
                },
            )
            return {"user_id": user_id, "name": "Test User"}

    try:
        return await circuit_breaker.call(simulate_db)
    except CircuitOpenError:
        logger.error(
            "Circuit open: DB unavailable",
            extra={"status_code": 503},
        )
        raise HTTPException(status_code=503, detail="Circuit open: DB unavailable")
    except DBTimeoutError:
        raise HTTPException(status_code=500, detail="DB connection timeout")


@app.post("/users/login")
async def login(request: LoginRequest):
    start = time.time()

    if random.random() < 0.10:
        await asyncio.sleep(random.uniform(1.5, 3))
        latency_ms = (time.time() - start) * 1000
        logger.warning(
            "Slow auth detected",
            extra={"latency_ms": latency_ms, "status_code": 200},
        )

    if random.random() < 0.08:
        LOGIN_FAILURES.labels(service="user-service").inc()
        logger.warning(
            "Login failed",
            extra={"status_code": 401},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    latency_ms = (time.time() - start) * 1000
    logger.info(
        "Login succeeded",
        extra={
            "endpoint": "/users/login",
            "status_code": 200,
            "latency_ms": latency_ms,
        },
    )
    return {"token": "fake-jwt", "user_id": str(uuid4())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
