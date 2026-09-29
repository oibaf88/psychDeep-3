"""PsychDeep vNext runtime configuration."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    database_url: str = "postgresql://psychapp:psychapp@db:5432/psychapp"
    database_schema: str = "psychdeep_v12"

    jwt_secret: str = "CHANGE_ME_DEV_ONLY_NOT_FOR_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    model_deployment_alias: str = "local-bridge"
    model_policy_version: str = "support-policy-v1"

    model_local_base_url: str = ""
    model_local_api_key: str = ""
    model_local_cf_access_required: bool = False
    model_local_cf_access_host: str = ""
    model_local_cf_access_client_id: str = ""
    model_local_cf_access_client_secret: str = ""
    model_local_chat_model: str = ""
    model_local_analysis_model: str = ""
    model_local_copilot_model: str = ""
    model_local_timeout_seconds: int = 120
    model_local_max_tokens: int = 8192

    local_bridge_enabled: bool = False
    local_bridge_secret: str = ""
    local_bridge_heartbeat_seconds: int = 20
    local_bridge_request_timeout_seconds: int = 600
    local_bridge_default_agent_id: str = "primary-windows"

    model_cloud_base_url: str = ""
    model_cloud_api_key: str = ""
    model_cloud_chat_model: str = ""
    model_cloud_analysis_model: str = ""
    model_cloud_copilot_model: str = ""
    model_cloud_timeout_seconds: int = 45
    model_cloud_max_tokens: int = 8192

    model_allow_commercial: bool = False
    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-sonnet-4-6"
    anthropic_analysis_model: str = "claude-sonnet-4-6"
    anthropic_copilot_model: str = ""
    anthropic_max_tokens: int = 8192
    anthropic_max_tokens_chat: int = 0
    anthropic_max_tokens_analysis: int = 0
    anthropic_chat_effort: str = "medium"
    anthropic_analysis_effort: str = "high"
    anthropic_copilot_effort: str = ""

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-5.6-luna"
    openai_analysis_model: str = "gpt-5.6-luna"
    openai_copilot_model: str = ""
    openai_max_tokens: int = 8192
    openai_timeout_seconds: int = 120
    openai_chat_effort: str = "medium"
    openai_analysis_effort: str = "high"
    openai_copilot_effort: str = "medium"

    llm_default_provider: str = "anthropic"
    llm_openai_compatible_base_url: str = ""
    llm_openai_compatible_api_key: str = ""
    llm_openai_compatible_chat_model: str = "gemma-2-2b-it"
    llm_openai_compatible_analysis_model: str = "gemma-2-2b-it"
    llm_openai_compatible_copilot_model: str = ""
    llm_openai_compatible_timeout_seconds: int = 300
    llm_openai_compatible_max_tokens: int = 8192
    llm_allow_runtime_override: bool = False

    conversation_context_budget_tokens: int = 12000
    conversation_history_budget_tokens: int = 4000
    conversation_context_block_budget_tokens: int = 6500
    conversation_max_history_messages: int = 12
    conversation_max_output_tokens: int = 1536

    app_locale: str = "es-ES"
    app_env: str = "local"
    allow_mock_google_login: bool = False

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "psychapp@localhost"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    seed_demo_data: bool = True

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

    @property
    def is_production(self) -> bool:
        return self.app_env not in ("local", "dev", "development")


@lru_cache
def get_settings() -> Settings:
    return Settings()
