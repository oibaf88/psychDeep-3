"""Register the per-account LLM settings under the existing LLM router.

Importing this package occurs before the application registers llm_settings.
"""
from . import llm_settings as _llm_settings
from . import personal_llm as _personal_llm

_llm_settings.router.include_router(_personal_llm.router)
