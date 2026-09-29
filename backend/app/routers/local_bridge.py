from __future__ import annotations

import asyncio
import contextlib
import secrets as _secrets
import time

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
    expires_at_raw = websocket.query_params.get("expires_at", "")
    try:
        expires_at = int(expires_at_raw)
    except ValueError:
        expires_at = 0

    now = int(time.time())
    if (
        not agent_id
        or len(agent_id) > 128
        or not challenge
        or len(challenge) > 256
        or expires_at < now
        or expires_at > now + 120
    ):
        await websocket.close(code=1008)
        return

    signed_handshake = {
        "agent_id": agent_id,
        "challenge": challenge,
        "expires_at": expires_at,
    }
    expected = sign_message(secret, signed_handshake)
    if not _secrets.compare_digest(token, expected):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    bridge = get_local_inference_bridge()
    queue = await bridge.register(agent_id)

    async def receive_message(message: dict) -> None:
        message_type = message.get("type")
        if message_type == "heartbeat":
            signed = {k: v for k, v in message.items() if k != "signature"}
            if verify_message(secret, signed, message.get("signature", "")):
                await bridge.heartbeat(agent_id)
            return

        if message_type != "inference_result":
            return

        signed = {k: v for k, v in message.items() if k != "signature"}
        if not verify_message(secret, signed, message.get("signature", "")):
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
            await websocket.send_json(
                {
                    **payload_for_agent,
                    "signature": sign_message(secret, payload_for_agent),
                }
            )

    try:
        await websocket.send_json({"type": "ready", "agent_id": agent_id})
        sender_task = asyncio.create_task(sender())
        try:
            while True:
                incoming = await websocket.receive_json()
                if isinstance(incoming, dict):
                    await receive_message(incoming)
        finally:
            sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender_task
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await bridge.unregister(agent_id)


@router.get("/status")
async def bridge_status(x_local_bridge_probe: str | None = Header(default=None)):
    if x_local_bridge_probe != _secret()[:12]:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return await get_local_inference_bridge().status()
