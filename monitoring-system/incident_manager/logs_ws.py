import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from es_logs import search_logs

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/logs/live")
async def logs_live(websocket: WebSocket):
    await websocket.accept()
    service = "user-service"
    level = ""
    search_text = ""
    auto_scroll = True

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=0.05)
                service = msg.get("service", service)
                level = msg.get("level", level)
                search_text = msg.get("search", search_text)
                auto_scroll = msg.get("auto_scroll", auto_scroll)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                raise

            logs = await search_logs(
                service=service or None,
                level=level or None,
                search_text=search_text or None,
                limit=100,
            )
            await websocket.send_json({"logs": logs, "auto_scroll": auto_scroll})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("Log websocket client disconnected")
    except Exception as exc:
        logger.error(f"Log websocket error: {exc}")
        try:
            await websocket.close()
        except Exception:
            pass
