"""Register account-scoped LLM settings on the settings router."""
from . import llm_settings as _llm_settings
from . import personal_llm as _personal_llm

_llm_settings.router.include_router(_personal_llm.router)
