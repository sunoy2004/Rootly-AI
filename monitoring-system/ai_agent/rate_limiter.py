import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable


logger = logging.getLogger(__name__)


class AIRateLimiter:
    def __init__(self, max_per_minute: int = 5):
        self.max_per_minute = max_per_minute
        self.call_timestamps: deque = deque()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.time()
            while (
                self.call_timestamps
                and self.call_timestamps[0] < now - 60
            ):
                self.call_timestamps.popleft()

            if len(self.call_timestamps) >= self.max_per_minute:
                wait_time = 60 - (now - self.call_timestamps[0])
                logger.warning(f"Rate limit reached. Waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

            self.call_timestamps.append(time.time())

    async def run_with_limit(
        self, func: Callable, *args: Any, **kwargs: Any
    ) -> Any:
        await self.acquire()
        return await func(*args, **kwargs)
