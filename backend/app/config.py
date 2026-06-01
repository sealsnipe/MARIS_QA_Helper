from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    CHAT_MODEL: str = "gpt-4.1-mini"
    TOP_K_DEFAULT: int = 6
    MIN_SCORE_DEFAULT: float = 0.25
    MAX_TOOL_ROUNDS: int = 4
    MAX_UPLOAD_MB: int = 30
    ALLOWED_EXTENSIONS: str = ".txt,.md,.pdf,.docx"

    @field_validator("SESSION_SECRET", "OPENAI_API_KEY")
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @property
    def allowed_extensions(self) -> set[str]:
        return {ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",") if ext.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
