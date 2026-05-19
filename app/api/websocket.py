import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.core.config import settings
from app.core.redis_client import get_redis

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def _verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


@router.websocket("/ws/feed")
async def websocket_feed(
    websocket: WebSocket,
    token: str = Query(...),
):
    username = _verify_token(token)
    if not username:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket)
    redis = await get_redis()

    await websocket.send_text(json.dumps({
        "type": "connected",
        "message": f"FlowEngine live feed connected. Welcome {username}",
    }))

    pubsub = redis.pubsub()
    await pubsub.subscribe("job_updates")

    try:
        async def listen():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await websocket.send_text(json.dumps({
                        "type": "job_update",
                        **data,
                    }))

        async def heartbeat():
            while True:
                await asyncio.sleep(15)
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break

        await asyncio.gather(listen(), heartbeat())

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await pubsub.unsubscribe("job_updates")
    except Exception:
        manager.disconnect(websocket)
        await pubsub.unsubscribe("job_updates")


@router.websocket("/ws/job/{job_id}")
async def websocket_job(
    websocket: WebSocket,
    job_id: str,
    token: str = Query(...),
):
    """Track a single job's status in real time."""
    username = _verify_token(token)
    if not username:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    redis = await get_redis()

    pubsub = redis.pubsub()
    await pubsub.subscribe("job_updates")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                if data.get("job_id") == job_id:
                    await websocket.send_text(json.dumps(data))
                    if data.get("status") in ("completed", "failed"):
                        break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("job_updates")
        await websocket.close()
