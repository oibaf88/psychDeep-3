"""Whether inference is scoped to the authenticated account.

`llm_config.resolve` reads this directly. There is no import-time patch.
"""
from __future__ import annotations

import os


def personal_mode_enabled() -> bool:
    return os.environ.get("LLM_PERSONAL_MODE", "").strip().lower() in ("1", "true", "yes")
