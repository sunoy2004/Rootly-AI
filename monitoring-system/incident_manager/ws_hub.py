import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from es_logs import search_logs

logger = logging.getLogger(__name__)

router = APIRouter()


class EventBroadcaster:
    """Fan-out Redis events and polled data to dashboard websocket clients."""

    def __init__(self):
        self.log_clients: Set[WebSocket] = set()
        self.anomaly_clients: Set[WebSocket] = set()
        self.incident_clients: Set[WebSocket] = set()

    async def _send(self, clients: Set[WebSocket], payload: dict):
        dead = set()
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        clients -= dead

    async def broadcast_anomaly(self, anomaly: dict):
        await self._send(self.anomaly_clients, {"type": "anomaly", "anomaly": anomaly})

    async def broadcast_incident(self, incident: dict):
        await self._send(self.incident_clients, {"type": "incident", "incident": incident})


broadcaster = EventBroadcaster()


async def _logs_loop(websocket: WebSocket, service: str, level: str, search: str):
    while True:
        try:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=0.05)
                service = msg.get("service", service)
                level = msg.get("level", level)
                search = msg.get("search", search)
            except asyncio.TimeoutError:
                pass

            try:
                logs = await asyncio.wait_for(
                    search_logs(
                        service=service or None,
                        level=level or None,
                        search_text=search or None,
                        limit=50,
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logs = []
            await websocket.send_json({"type": "logs", "logs": logs})
            logger.debug(f"WS /ws/logs sent {len(logs)} logs service={service}")
            await asyncio.sleep(2)
        except WebSocketDisconnect:
            raise
        except Exception as exc:
            logger.error(f"Log stream error: {exc}")
            await asyncio.sleep(2)


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    broadcaster.log_clients.add(websocket)
    logger.info("WS client connected: /ws/logs")
    service, level, search = "user-service", "", ""
    try:
        try:
            init = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
            service = init.get("service", service)
            level = init.get("level", level)
            search = init.get("search", search)
        except (asyncio.TimeoutError, WebSocketDisconnect):
            pass
        await _logs_loop(websocket, service, level, search)
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.log_clients.discard(websocket)
        logger.info("WS client disconnected: /ws/logs")


@router.websocket("/logs/live")
async def ws_logs_legacy(websocket: WebSocket):
    await ws_logs(websocket)


@router.websocket("/ws/anomalies")
async def ws_anomalies(websocket: WebSocket):
    await websocket.accept()
    broadcaster.anomaly_clients.add(websocket)
    logger.info("WS client connected: /ws/anomalies")
    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.anomaly_clients.discard(websocket)


@router.websocket("/ws/incidents")
async def ws_incidents(websocket: WebSocket):
    await websocket.accept()
    broadcaster.incident_clients.add(websocket)
    logger.info("WS client connected: /ws/incidents")
    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.incident_clients.discard(websocket)


async def redis_event_bridge(redis_url: str):
    """Forward Redis pub/sub events to websocket clients."""
    import redis.asyncio as aioredis

    channels = [
        "anomaly_events",
        "ai_analysis_completed",
        "incidents_to_alert",
        "rule_matches",
    ]
    backoff = 1
    while True:
        try:
            client = await aioredis.from_url(redis_url)
            pubsub = client.pubsub()
            await pubsub.subscribe(*channels)
            backoff = 1
            logger.info(f"Redis bridge subscribed: {channels}")
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                try:
                    data = json.loads(message["data"])
                except json.JSONDecodeError:
                    continue

                if channel == "anomaly_events":
                    await broadcaster.broadcast_anomaly(data)
                elif channel in ("ai_analysis_completed", "incidents_to_alert", "rule_matches"):
                    incident = data.get("incident", data)
                    await broadcaster.broadcast_incident(incident)
        except Exception as exc:
            logger.error(f"Redis bridge error: {exc}, retry in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
