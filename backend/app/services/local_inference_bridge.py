"""Outbound local inference bridge.

The Windows/local agent initiates the connection to Render. Render never
opens an inbound connection to the user's LAN. Inference payloads and results
therefore travel over one authenticated TLS channel in both directions.

The transport is intentionally independent from SSH and Cloudflare Tunnel.
The local agent may sit behind CGNAT, NAT or a restrictive residential
firewall as long as it can make outbound HTTPS/WebSocket connections.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.config import get_settings

logger = logging.getLogger("psychapp.local_bridge")


@dataclass(frozen=True)
class LocalBridgeConfig:
    enabled: bool
    shared_secret: str
    heartbeat_seconds: int
    request_timeout_seconds: int

    @classmethod
    def from_settings(cls) -> "LocalBridgeConfig":
        settings = get_settings()
        return cls(
            enabled=settings.local_bridge_enabled,
            shared_secret=settings.local_bridge_secret.strip(),
            heartbeat_seconds=settings.local_bridge_heartbeat_seconds,
            request_timeout_seconds=settings.local_bridge_request_timeout_seconds,
        )

    def validate(self) -> None:
        if not self.enabled:
            raise RuntimeError("LOCAL_BRIDGE_DISABLED")
        if len(self.shared_secret) < 32:
            raise RuntimeError("LOCAL_BRIDGE_SECRET_INVALID")


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sign_message(secret: str, payload: dict[str, Any]) -> str:
    return hmac.new(secret.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()


def verify_message(secret: str, payload: dict[str, Any], signature: str) -> bool:
    expected = sign_message(secret, payload)
    return hmac.compare_digest(expected, signature)


class LocalInferenceBridge:
    """In-memory broker for an outbound local agent connection."""

    def __init__(self, config: LocalBridgeConfig | None = None) -> None:
        self.config = config or LocalBridgeConfig.from_settings()
        self.config.validate()
        self._agents: dict[str, "asyncio.Queue[dict[str, Any]]"] = {}
        self._results: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def register(self, agent_id: str) -> asyncio.Queue[dict[str, Any]]:
        if not agent_id or len(agent_id) > 128:
            raise ValueError("LOCAL_AGENT_ID_INVALID")
        async with self._lock:
            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=16)
            self._agents[agent_id] = queue
            return queue

    async def unregister(self, agent_id: str) -> None:
        async with self._lock:
            self._agents.pop(agent_id, None)

    async def submit(
        self,
        *,
        request: dict[str, Any],
        agent_id: str,
    ) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        message = {
            "type": "inference_request",
            "request_id": request_id,
            "created_at": time.time(),
            "payload": request,
        }
        async with self._lock:
            queue = self._agents.get(agent_id)
            if queue is None:
                raise RuntimeError("LOCAL_AGENT_OFFLINE")
            loop = asyncio.get_running_loop()
            future: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._results[request_id] = future
        try:
            await queue.put(message)
            return await asyncio.wait_for(
                future,
                timeout=self.config.request_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError("LOCAL_INFERENCE_TIMEOUT") from exc
        finally:
            async with self._lock:
                self._results.pop(request_id, None)

    async def resolve(self, request_id: str, result: dict[str, Any]) -> None:
        async with self._lock:
            future = self._results.get(request_id)
            if future is None or future.done():
                return
            future.set_result(result)

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "enabled": self.config.enabled,
                "connected_agents": sorted(self._agents.keys()),
            }


_bridge: LocalInferenceBridge | None = None


def get_local_inference_bridge() -> LocalInferenceBridge:
    global _bridge
    if _bridge is None:
        _bridge = LocalInferenceBridge()
    return _bridge
