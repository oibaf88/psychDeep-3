"""Compatibility bridge for existing callers of llm_config.resolve(db).

The old application has multiple inference paths (chat, analyzer, copilot,
trace). All MUST use the same account-scoped resolver before personal mode
is enabled; otherwise a global cached choice can cross account boundaries.
"""
from __future__ import annotations

import functools
import os

from app.services import llm_config, personal_llm


def personal_mode_enabled() -> bool:
    return os.environ.get("LLM_PERSONAL_MODE", "").strip().lower() in ("1", "true", "yes")


def install() -> None:
    """Install once, before routers start handling requests.

    This narrow bridge preserves the pre-migration behavior until the operator
    explicitly enables LLM_PERSONAL_MODE. It must be retired when the old global
    llm_config API is removed in a separate compatibility cleanup.
    """
    original = llm_config.resolve
    if getattr(original, "_personal_scoped", False):
        return

    @functools.wraps(original)
    def resolve_for_request(db=None):
        if not personal_mode_enabled():
            return original(db)
        if db is None:
            # Health/CLI must not masquerade as an authenticated user. No
            # request-level inference should call this without its Session.
            return original(db)
        info = getattr(db, "info", None)
        user_id = info.get("authenticated_user_id") if isinstance(info, dict) else None
        if user_id is None:
            raise RuntimeError("Inferencia bloqueada: no existe identidad de cuenta verificada.")
        # Never enter llm_config's process-wide cache for account selections.
        return personal_llm.resolve(db, user_id)

    resolve_for_request._personal_scoped = True
    llm_config.resolve = resolve_for_request
