import asyncio

from app.services.local_inference_bridge import (
    LocalBridgeConfig,
    LocalInferenceBridge,
    sign_message,
    verify_message,
)


def test_bridge_signatures_are_deterministic_and_verified():
    payload = {"agent_id": "primary-windows", "challenge": "abc", "expires_at": 123}
    secret = "x" * 48
    signature = sign_message(secret, payload)

    assert verify_message(secret, payload, signature)
    assert not verify_message(secret, {**payload, "expires_at": 124}, signature)


def test_bridge_submit_and_resolve_round_trip():
    async def scenario():
        bridge = LocalInferenceBridge(
            LocalBridgeConfig(
                enabled=True,
                shared_secret="x" * 48,
                heartbeat_seconds=20,
                request_timeout_seconds=5,
            )
        )
        queue = await bridge.register("primary-windows")

        async def worker():
            request = await queue.get()
            await bridge.resolve(
                request["request_id"],
                {"text": "respuesta local", "model": "gemma"},
            )

        worker_task = asyncio.create_task(worker())
        result = await bridge.submit(
            request={"kind": "chat", "messages": [{"role": "user", "content": "hola"}]},
            agent_id="primary-windows",
        )
        await worker_task
        assert result["text"] == "respuesta local"

    asyncio.run(scenario())
