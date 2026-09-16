"""Register account-scoped LLM settings and select the per-request resolver."""
from . import llm_settings as _llm_settings
from . import personal_llm as _personal_llm
from app.services.personal_resolution import install as _install_personal_resolution

_install_personal_resolution()
_llm_settings.router.include_router(_personal_llm.router)
