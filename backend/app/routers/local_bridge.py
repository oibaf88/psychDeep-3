from __future__ import annotations

import secrets as _secrets

from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.local_inference_bridge import (
    get_local_inference_bridge,
    sign_message,
    verify_message,
)

router = APIRouter(prefix="/local-bridge", tags=["local-bridge"])


def _secret() -> str:
    secret = get_settings().local_bridge_secret.strip()
    if not secret or len(secret) < 32:
        raise HTTPException(status_code=503, detail="Local inference bridge is not configured.")
    return secret


@router.websocket("/connect")
async def connect_agent(websocket: WebSocket):
    settings = get_settings()
    secret = settings.local_bridge_secret.strip()
    if not settings.local_bridge_enabled or len(secret) < 32:
        await websocket.close(code=1013)
        return

    token = websocket.query_params.get("token", "")
    agent_id = websocket.query_params.get("agent_id", "")
    challenge = websocket.query_params.get("challenge", "")
    if not agent_id or len(agent_id) > 128 or not challenge or len(challenge) > 256:
        await websocket.close(code=1008)
        return

    expected = sign_message(secret, {"agent_id": agent_id, "challenge": challenge})
    if not _secrets.compare_digest(token, expected):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    bridge = get_local_inference_bridge()
    queue = await bridge.register(agent_id)

    async def receive_result(message: dict) -> None:
        if message.get("type") != "inference_result":
            return
        signature = message.get("signature", "")
        clean = {k: v for k, v in message.items() if k != "signature"}
        if not verify_message(secret, clean, signature):
            return
        request_id = message.get("request_id")
        result = message.get("result")
        if isinstance(request_id, str) and isinstance(result, dict):
            await bridge.resolve(request_id, result)

    async def sender() -> None:
        while True:
            outgoing = await queue.get()
            payload_for_agent = {
                "type": outgoing["type"],
                "request_id": outgoing["request_id"],
                "payload": outgoing["payload"],
            }
            signature = sign_message(secret, payload_for_agent)
            await websocket.send_json({**payload_for_agent, "signature": signature})

    try:
        await websocket.send_json({"type": "ready", "agent_id": agent_id})
        sender_task = __import__("asyncio").create_task(sender())
        try:
            while True:
                incoming = await websocket.receive_json()
                await receive_result(incoming)
        finally:
            sender_task.cancel()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await bridge.unregister(agent_id)


@router.get("/status")
async def bridge_status(x_local_bridge_probe: str | None = Header(default=None)):
    if x_local_bridge_probe != _secret()[:12]:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return await get_local_inference_bridge().status()
