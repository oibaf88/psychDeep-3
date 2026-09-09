"""Smoke-check the selected Claude or Gemma 2 provider without database writes.

Run from ``backend/`` against Claude via the server secret, local LM Studio,
or the authenticated Cloudflare Tunnel endpoint. It sends two short synthetic
strings only and exits non-zero if chat or structured analysis fails.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content.prompts import AGENT1_SYSTEM_PROMPT, AGENT2_SYSTEM_PROMPT, AGENT2_TOOL_SCHEMA  # noqa: E402
from app.services import llm_config  # noqa: E402
from app.services.llm import get_llm_provider  # noqa: E402

SAMPLE_TEXT = "He dormido poco esta semana y estoy cansado, pero hoy quiero descansar y pedir apoyo."
EXPECTED_FIELDS = set(AGENT2_TOOL_SCHEMA["input_schema"]["properties"])


def main() -> int:
    active = llm_config.resolve()
    if active.provider == llm_config.PROVIDER_ANTHROPIC and not active.api_key:
        print("FAIL  Configura ANTHROPIC_API_KEY como secreto del servidor antes de ejecutar la prueba.")
        return 1
    if active.provider == llm_config.PROVIDER_LOCAL and (not active.base_url or not active.api_key):
        print("FAIL  Configura la URL /v1 y el token de LM Studio para Gemma 2 antes de ejecutar la prueba.")
        return 1

    print(f"chat model     : {active.chat_model}")
    print(f"analysis model : {active.analysis_model}")
    provider = get_llm_provider()
    ok = True

    try:
        reply = provider.chat(AGENT1_SYSTEM_PROMPT, [{"role": "user", "content": SAMPLE_TEXT}], max_tokens=300)
        if not reply.text.strip():
            raise RuntimeError("empty reply")
        print(f"PASS  Agent 1 ({active.provider} conversation)")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"FAIL  Agent 1: {type(exc).__name__}: {exc}")

    try:
        analysis = provider.analyze_structured(AGENT2_SYSTEM_PROMPT, SAMPLE_TEXT, AGENT2_TOOL_SCHEMA)
        missing = EXPECTED_FIELDS - set(analysis.value)
        if missing:
            raise RuntimeError(f"missing fields: {sorted(missing)}")
        print(f"PASS  Agent 2 ({active.provider} structured analysis)")
        print(json.dumps(analysis.value, ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"FAIL  Agent 2: {type(exc).__name__}: {exc}")

    print("RESULT:", "both agents OK" if ok else "at least one agent is broken")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
