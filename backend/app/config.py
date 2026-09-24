"""PsychDeep vNext runtime configuration.

Clinical data can be processed either by the cloud API or by an approved
on-device inference runtime. Desktop local models remain available through
an authenticated HTTPS tunnel. Secrets are deployment environment variables
and are never persisted in clinical DB configuration rows.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=("settings_",))

    # --- Database: cloud source of truth ---------------------------------
    database_url: str = "postgresql://psychapp:psychapp@db:5432/psychapp"
    database_schema: str = ""

    # --- Auth -------------------------------------------------------------
    jwt_secret: str = "CHANGE_ME_DEV_ONLY_NOT_FOR_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    # --- vNext Model Gateway ---------------------------------------------
    # Deployment default. When LLM_ALLOW_RUNTIME_OVERRIDE=true, only an
    # admin_clinical account may explicitly supersede it with another approved
    # provider. There is never an automatic provider fallback.
    model_deployment_alias: str = "local-tunnel"
    model_policy_version: str = "support-policy-v1"

    # Profile A: user-controlled OpenAI-compatible model via authenticated
    # HTTPS tunnel. Legacy LLM_* names remain fallbacks during the transition
    # so an existing Render deployment does not lose its endpoint.
    model_local_base_url: str = ""
    model_local_api_key: str = ""  # Legacy/fallback for endpoints not using Access.
    # Access service credentials are NOT the cloudflared connector token/secret.
    # When required, absent/partial credentials cause the local provider to fail
    # closed. The hostname must match the HTTPS model endpoint exactly.
    model_local_cf_access_required: bool = False
    model_local_cf_access_host: str = ""
    model_local_cf_access_client_id: str = ""
    model_local_cf_access_client_secret: str = ""
    model_local_chat_model: str = ""
    model_local_analysis_model: str = ""
    model_local_copilot_model: str = ""
    model_local_timeout_seconds: int = 45
    model_local_max_tokens: int = 8192

    # Profile B: managed/private cloud tuned endpoint. Kept disabled until an
    # approved model/version is configured and promoted through evaluation.
    model_cloud_base_url: str = ""
    model_cloud_api_key: str = ""
    model_cloud_chat_model: str = ""
    model_cloud_analysis_model: str = ""
    model_cloud_copilot_model: str = ""
    model_cloud_timeout_seconds: int = 45
    model_cloud_max_tokens: int = 8192

    # Optional commercial deployment. It is selectable only when explicitly
    # approved by MODEL_ALLOW_COMMERCIAL; vNext never silently fails over to it.
    model_allow_commercial: bool = False
    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-3-5-sonnet"
    anthropic_analysis_model: str = "claude-3-5-sonnet"
    anthropic_copilot_model: str = ""
    anthropic_max_tokens: int = 8192
    anthropic_max_tokens_chat: int = 0
    anthropic_max_tokens_analysis: int = 0
    anthropic_chat_effort: str = "medium"
    anthropic_analysis_effort: str = "high"
    anthropic_copilot_effort: str = ""

    # Legacy compatibility inputs plus the deployment-level runtime-switch
    # gate. False remains the fail-safe library default; production Render sets
    # LLM_ALLOW_RUNTIME_OVERRIDE=true explicitly.
    llm_default_provider: str = "anthropic"
    llm_openai_compatible_base_url: str = ""
    llm_openai_compatible_api_key: str = ""
    llm_openai_compatible_chat_model: str = "gemma-2-2b-it"
    llm_openai_compatible_analysis_model: str = "gemma-2-2b-it"
    llm_openai_compatible_copilot_model: str = ""
    llm_openai_compatible_timeout_seconds: int = 300
    llm_openai_compatible_max_tokens: int = 8192
    llm_allow_runtime_override: bool = False

    @property
    def local_base_url(self) -> str:
        return self.model_local_base_url.strip() or self.llm_openai_compatible_base_url.strip()

    @property
    def local_api_key(self) -> str:
        return self.model_local_api_key or self.llm_openai_compatible_api_key

    @property
    def local_chat_model(self) -> str:
        return self.model_local_chat_model.strip() or self.llm_openai_compatible_chat_model

    @property
    def local_analysis_model(self) -> str:
        return self.model_local_analysis_model.strip() or self.llm_openai_compatible_analysis_model

    @property
    def local_copilot_model(self) -> str:
        return (
            self.model_local_copilot_model.strip()
            or self.llm_openai_compatible_copilot_model.strip()
            or self.local_chat_model
        )

    @property
    def copilot_model(self) -> str:
        return self.anthropic_copilot_model.strip() or self.anthropic_chat_model

    @property
    def copilot_effort(self) -> str:
        return self.anthropic_copilot_effort.strip() or self.anthropic_chat_effort

    @property
    def max_tokens_chat(self) -> int:
        return self.anthropic_max_tokens_chat or self.anthropic_max_tokens

    @property
    def max_tokens_analysis(self) -> int:
        return self.anthropic_max_tokens_analysis or self.anthropic_max_tokens

    # --- App --------------------------------------------------------------
    app_locale: str = "es-ES"
    app_env: str = "local"
    allow_mock_google_login: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env not in ("local", "dev", "development")

    # --- Notifications ----------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "psychapp@localhost"

    # --- CORS -------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Seed -------------------------------------------------------------
    seed_demo_data: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
