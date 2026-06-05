from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMAuthMode = Literal["api_key", "chatgpt_oauth"]

IMAGE_UPLOAD_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8088
    SESSION_SECRET: str
    DATABASE_URL: str = "sqlite:///./data/support_kb.sqlite3"
    QDRANT_URL: str = "http://qdrant:6333"
    COLLECTION_PREFIX: str = "kb_"
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    LLM_AUTH_MODE: LLMAuthMode = "chatgpt_oauth"
    CHAT_MODEL: str = "gpt-4.1-mini"
    VISION_MODEL: str = "gpt-5.4-mini"
    VISION_MAX_IMAGES: int = 20
    VISION_ENABLED: bool = True
    CODEX_AUTH_PATH: str = "~/.codex/auth.json"
    CODEX_OAUTH_AUTH_PATH: str = "~/.oauth_codex/auth.json"
    CODEX_BASE_URL: str = "https://chatgpt.com/backend-api/codex"
    MARIS_OAUTH_DIR: str = "~/.maris/oauth"
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    SESSION_COOKIE_SECURE: bool = False
    TOP_K_DEFAULT: int = 4
    MIN_SCORE_DEFAULT: float = 0.25
    DUPLICATE_SIMILAR_MIN_SCORE: float = 0.92
    DUPLICATE_SIMILAR_TOP_K: int = 3
    MERGE_BLOCK_MIN_SCORE: float = 0.85
    MERGE_UNCHANGED_SCORE: float = 0.98
    MERGE_LLM_ENABLED: bool = True
    MERGE_LLM_MIN_CONFIDENCE: float = 0.65
    MERGE_LLM_MAX_CHARS: int = 24000
    MAX_TOOL_ROUNDS: int = 4
    MAX_UPLOAD_MB: int = 30
    ALLOWED_EXTENSIONS: str = ".txt,.md,.pdf,.docx,.png,.jpg,.jpeg,.webp,.gif"
    INTEGRATION_API_TOKEN: str = ""
    INTEGRATION_USER_EMAIL: str = "integration@internal"

    @field_validator("SESSION_SECRET", "OPENAI_API_KEY")
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @property
    def allowed_extensions(self) -> set[str]:
        configured = {ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",") if ext.strip()}
        return configured | set(IMAGE_UPLOAD_EXTENSIONS)

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def codex_oauth_auth_path(self) -> str:
        return str(Path(self.CODEX_OAUTH_AUTH_PATH).expanduser())

    @property
    def uses_chatgpt_oauth(self) -> bool:
        return self.LLM_AUTH_MODE == "chatgpt_oauth"

    @property
    def vision_enabled(self) -> bool:
        return self.VISION_ENABLED

    @property
    def vision_max_images(self) -> int:
        return max(1, self.VISION_MAX_IMAGES)

    @property
    def integration_enabled(self) -> bool:
        return bool(self.INTEGRATION_API_TOKEN.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
