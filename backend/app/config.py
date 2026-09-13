"""
PsychApp backend configuration.

All values are read from environment variables (see ../.env.example at the
project root). Nothing here should ever contain a real secret.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database -----------------------------------------------------
    database_url: str = "postgresql://psychapp:psychapp@db:5432/psychapp"
    database_schema: str = ""

    # --- Auth -----------------------------------------------------------
    jwt_secret: str = "CHANGE_ME_DEV_ONLY_NOT_FOR_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12  # 12h, local/demo convenience

    # --- LLM --------------------------------------------------------------
    # Claude through Anthropic is the connected-service default. Gemma 2
    # through an OpenAI-compatible server (LM Studio locally, the
    # authenticated Cloudflare hostname from Render) is the offline/local
    # alternative.
    # Claude is the primary connected-service default.  A local/offline
    # deployment explicitly overrides this to Gemma 2 in `.env.local`.
    llm_default_provider: str = "anthropic"
    llm_openai_compatible_base_url: str = ""
    llm_openai_compatible_api_key: str = ""
    llm_openai_compatible_chat_model: str = "gemma-2-2b-it"
    llm_openai_compatible_analysis_model: str = "gemma-2-2b-it"
    llm_openai_compatible_copilot_model: str = ""
    llm_openai_compatible_timeout_seconds: int = 300
    llm_openai_compatible_max_tokens: int = 8192

    # Optional remote alternative.  The key is deployment-only: runtime
    # configuration may select Claude but can never receive or replace it.
    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-opus-5"
    anthropic_analysis_model: str = "claude-opus-5"
    anthropic_copilot_model: str = ""
    anthropic_max_tokens: int = 8192
    anthropic_max_tokens_chat: int = 0
    anthropic_max_tokens_analysis: int = 0
    anthropic_chat_effort: str = "medium"
    anthropic_analysis_effort: str = "high"
    anthropic_copilot_effort: str = ""

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
    def local_copilot_model(self) -> str:
        return self.llm_openai_compatible_copilot_model.strip() or self.llm_openai_compatible_chat_model

    # --- Runtime LLM endpoint override ----------------------------------
    # Lets the two inference agents be pointed at a model you host yourself
    # (llama.cpp, Ollama, LM Studio, vLLM) from the Settings screen, without
    # redeploying, so a local model can be tried against the real app.
    #
    # The server fetches whatever URL is configured, so this is genuinely a
    # deployment decision and not only a UI one: patient text is sent to that
    # endpoint, and Agent 2's ability to spot a linguistic risk marker
    # becomes a property of the model behind it.
    #
    # Off by default. A deployment where the people using the app are not the
    # people running it must never expose this, and defaulting to on meant a
    # deployment that simply never mentioned the variable — as this repo's
    # own render.yaml did — shipped with it enabled. Turning it on is now a
    # deliberate act. Even then only `admin_clinical` may write (see
    # routers/llm_settings.py), and every change goes to the audit log.
    llm_allow_runtime_override: bool = False

    # --- App / locale -----------------------------------------------------
    app_locale: str = "es-ES"
    app_env: str = "local"

    # --- Unfinished auth features (off by default) ----------------------
    # /auth/google-login currently trusts the client-supplied id_token as
    # the user's email instead of verifying it with Google, so enabling it
    # lets anyone obtain a session for any account. Keep it false until
    # real Google verification is implemented.
    allow_mock_google_login: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env not in ("local", "dev", "development")

    # --- Notifications (all optional; app works with none configured) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "psychapp@localhost"

    # --- CORS -------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Seed data ----------------------------------------------------
    seed_demo_data: bool = True
    demo_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
