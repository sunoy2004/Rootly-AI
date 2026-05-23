import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from engine import RuleEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


rule_engine: Optional[RuleEngine] = None
background_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rule_engine, background_task
    rule_engine = RuleEngine()
    background_task = asyncio.create_task(rule_engine.start())
    yield
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Rule Engine", lifespan=lifespan)


@app.get("/health")
async def health():
    rules_loaded = len(rule_engine.evaluator.rules) if rule_engine else 0
    return {
        "status": "ok",
        "service": "rule-engine",
        "rules_loaded": rules_loaded,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
