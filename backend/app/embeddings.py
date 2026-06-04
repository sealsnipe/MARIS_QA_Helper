from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings


class EmbeddingsBackend(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass
class OpenAIEmbeddings:
    api_key: str
    base_url: str
    model: str
    expected_dim: int

    def __post_init__(self) -> None:
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self.model, input=texts)
        vectors = [item.embedding for item in response.data]
        for vector in vectors:
            if len(vector) != self.expected_dim:
                raise RuntimeError("embedding_dim_mismatch")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0]


_embeddings_backend: EmbeddingsBackend | None = None


def get_embeddings_backend(db: Session | None = None) -> EmbeddingsBackend:
    global _embeddings_backend
    if _embeddings_backend is None:
        from app.secrets_admin import get_effective_secret

        settings = get_settings()
        key = get_effective_secret(db, "embedding_api_key") or settings.OPENAI_API_KEY
        _embeddings_backend = OpenAIEmbeddings(
            api_key=key,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            expected_dim=settings.EMBEDDING_DIM,
        )
    return _embeddings_backend


def set_embeddings_backend(backend: EmbeddingsBackend | None) -> None:
    global _embeddings_backend
    _embeddings_backend = backend
