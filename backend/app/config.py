"""Application configuration loaded from environment variables (12-factor)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RecruiMate"
    environment: str = "development"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'recruimate.db'}"
    upload_dir: str = str(BASE_DIR / "data" / "uploads")
    max_upload_mb: int = 10
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional bearer token. When empty the app runs in trusted local mode.
    api_token: str = ""

    # --- Authentication ------------------------------------------------------
    # Set AUTH_ENABLED=true to turn on the account system (register/login/JWT).
    # While false the app stays in trusted-local mode for backwards compatibility.
    auth_enabled: bool = False
    jwt_secret: str = "change-me-local-dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 30
    # When true, demo accounts (candidate1..5) are created on first boot.
    seed_demo_accounts: bool = True
    demo_account_password: str = "RecruiMate@123"

    # Default provider ("heuristic" works fully offline; configure a real one in Settings)
    default_provider: str = "heuristic"
    request_timeout: float = 60.0
    max_retries: int = 2
    # Never silently move to a paid model when a free one fails.
    allow_paid_fallback: bool = False

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"

    # Groq
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    # Gemini
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"

    # Self-hosted OpenCode server (session API, not OpenAI-compatible)
    opencode_base_url: str = "http://127.0.0.1:8080"
    opencode_username: str = "opencode"
    opencode_password: str = ""
    opencode_model: str = "opencode"

    # Ollama (OpenAI compatible)
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "llama3.2"

    # Custom OpenAI-compatible providers may only target these hosts.
    allowed_custom_hosts: str = "localhost,127.0.0.1,::1"
    allow_private_hosts: bool = True

    # Embeddings: "auto" uses sentence-transformers when installed, else hashed TF-IDF.
    embeddings_backend: str = "auto"
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
