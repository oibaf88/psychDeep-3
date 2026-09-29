"""Outbound local inference bridge.

The local agent initiates the connection to Render. Render never opens an
inbound connection to the user's LAN. The existing synchronous application
pipeline can wait on the bridge without changing every router to async.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import hmac
import json
import logging
import queue
import threading
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
    return hmac.new(
        secret.encode("utf-8"),
        _canonical(payload),
        hashlib.sha256,
    ).hexdigest()


def verify_message(secret: str, payload: dict[str, Any], signature: str) -> bool:
    return hmac.compare_digest(sign_message(secret, payload), signature)


class LocalInferenceBridge:
    """Thread-safe broker shared by sync API code and async WebSocket code."""

    def __init__(self, config: LocalBridgeConfig | None = None) -> None:
        self.config = config or LocalBridgeConfig.from_settings()
        self.config.validate()
        self._agents: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._results: dict[str, concurrent.futures.Future[dict[str, Any]]] = {}
        self._heartbeats: dict[str, float] = {}
        self._lock = threading.RLock()

    def register_sync(self, agent_id: str) -> queue.Queue[dict[str, Any]]:
        if not agent_id or len(agent_id) > 128:
            raise ValueError("LOCAL_AGENT_ID_INVALID")
        with self._lock:
            q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=16)
            self._agents[agent_id] = q
            self._heartbeats[agent_id] = time.time()
            return q

    async def register(self, agent_id: str) -> queue.Queue[dict[str, Any]]:
        return self.register_sync(agent_id)

    def unregister_sync(self, agent_id: str) -> None:
        with self._lock:
            self._agents.pop(agent_id, None)
            self._heartbeats.pop(agent_id, None)

    async def unregister(self, agent_id: str) -> None:
        self.unregister_sync(agent_id)

    def heartbeat_sync(self, agent_id: str) -> None:
        with self._lock:
            if agent_id in self._agents:
                self._heartbeats[agent_id] = time.time()

    async def heartbeat(self, agent_id: str) -> None:
        self.heartbeat_sync(agent_id)

    def submit_sync(self, *, request: dict[str, Any], agent_id: str) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        with self._lock:
            q = self._agents.get(agent_id)
            if q is None:
                raise RuntimeError("LOCAL_AGENT_OFFLINE")
            future: concurrent.futures.Future[dict[str, Any]] = concurrent.futures.Future()
            self._results[request_id] = future
            q.put(
                {
                    "type": "inference_request",
                    "request_id": request_id,
                    "created_at": time.time(),
                    "payload": request,
                }
            )
        try:
            result = future.result(timeout=self.config.request_timeout_seconds)
            if isinstance(result, dict) and result.get("error"):
                raise RuntimeError(str(result["error"]))
            return result
        except concurrent.futures.TimeoutError as exc:
            raise RuntimeError("LOCAL_INFERENCE_TIMEOUT") from exc
        finally:
            with self._lock:
                self._results.pop(request_id, None)

    async def submit(self, *, request: dict[str, Any], agent_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.submit_sync,
            request=request,
            agent_id=agent_id,
        )

    def resolve_sync(self, request_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            future = self._results.get(request_id)
            if future is None or future.done():
                return
            future.set_result(result)

    async def resolve(self, request_id: str, result: dict[str, Any]) -> None:
        self.resolve_sync(request_id, result)

    async def status(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            live_after = max(self.config.heartbeat_seconds * 3, 60)
            connected = sorted(
                agent_id
                for agent_id, heartbeat in self._heartbeats.items()
                if now - heartbeat <= live_after
            )
            return {
                "enabled": self.config.enabled,
                "connected_agents": connected,
            }


_bridge: LocalInferenceBridge | None = None


def get_local_inference_bridge() -> LocalInferenceBridge:
    global _bridge
    if _bridge is None:
        _bridge = LocalInferenceBridge()
    return _bridge
