import asyncio
import time
from typing import Any, Callable


CLOSED = "CLOSED"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 10,
        recovery_timeout: int = 30,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.lock = asyncio.Lock()

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        async with self.lock:
            if self.state == OPEN:
                if (
                    self.last_failure_time is not None
                    and time.time() - self.last_failure_time > self.recovery_timeout
                ):
                    self.state = HALF_OPEN
                else:
                    raise CircuitOpenError(f"{self.name} circuit open")

        try:
            result = await func(*args, **kwargs)
            async with self.lock:
                if self.state == HALF_OPEN:
                    self.state = CLOSED
                    self.failure_count = 0
            return result
        except Exception as exc:
            async with self.lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = OPEN
            raise

    def get_state(self) -> dict:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
        }
