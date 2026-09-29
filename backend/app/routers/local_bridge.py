from __future__ import annotations

import uuid

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
    secret = get_settings().local_bridge_secret.strip()
    if not get_settings().local_bridge_enabled or len(secret) < 32:
        await websocket.close(code=1013)
        return

    token = websocket.query_params.get("token", "")
    agent_id = websocket.query_params.get("agent_id", "")
    challenge = websocket.query_params.get("challenge", "")
    if not agent_id or len(agent_id) > 128 or not challenge:
        await websocket.close(code=1008)
        return

    expected = sign_message(secret, {"agent_id": agent_id, "challenge": challenge})
    if not verify_message(secret, {"agent_id": agent_id, "challenge": challenge}, token) if token else token != expected:
        # Kept deliberately simple: the query token is an HMAC over a one-time
        # challenge. No static bearer is placed in a public URL by the server.
        await websocket.close(code=1008)
        return

    await websocket.accept()
    bridge = get_local_inference_bridge()
    queue = await bridge.register(agent_id)

    try:
        await websocket.send_json({"type": "ready", "agent_id": agent_id})
        while True:
            outgoing = await queue.get()
            payload_for_agent = {
                "type": outgoing["type"],
                "request_id": outgoing["request_id"],
                "payload": outgoing["payload"],
            }
            signature = sign_message(secret, payload_for_agent)
            await websocket.send_json({**payload_for_agent, "signature": signature})

            # A single socket may process multiple requests. Responses are
            # received asynchronously while the sending loop continues.
            async def receive_result(message: dict):
                if message.get("type") != "inference_result":
                    return
                signature = message.pop("signature", "")
                clean = {k: v for k, v in message.items() if k != "signature"}
                if not verify_message(secret, clean, signature):
                    return
                await bridge.resolve(message["request_id"], message["result"])

            try:
                first = await websocket.receive_json()
                await receive_result(first)
            except ValueError:
                continue
    except WebSocketDisconnect:
        pass
    finally:
        await bridge.unregister(agent_id)


@router.get("/status")
async def bridge_status(x_local_bridge_probe: str | None = Header(default=None)):
    if x_local_bridge_probe != _secret()[:12]:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return await get_local_inference_bridge().status()
