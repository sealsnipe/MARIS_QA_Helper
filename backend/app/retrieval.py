from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import re

from app.customers import GLOBAL_CUSTOMER_ID, is_global_customer
from app.config import get_settings
from app.embeddings import EmbeddingsBackend, get_embeddings_backend
from app.prompts import NO_HITS_TEXT
from app.qdrant_store import SearchHit, VectorStore, get_vector_store


@dataclass
class RetrievalHit:
    document_id: str
    title: str
    chunk_index: int
    text: str
    score: float


def clamp_top_k(top_k: int | None, default: int) -> int:
    value = default if top_k is None else top_k
    return max(1, min(20, int(value)))


def search_knowledge_base(
    customer_id: str,
    query: str,
    top_k: int | None = None,
    *,
    min_score: float | None = None,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> list[RetrievalHit]:
    settings = get_settings()
    embeddings = embeddings or get_embeddings_backend()
    vector_store = vector_store or get_vector_store()
    limit = clamp_top_k(top_k, settings.TOP_K_DEFAULT)
    threshold = settings.MIN_SCORE_DEFAULT if min_score is None else min_score

    vector = embeddings.embed_query(query.strip())
    raw_hits = vector_store.search(customer_id, vector, limit)
    return _filter_hits(raw_hits, threshold)


def search_knowledge_base_scoped(
    customer_id: str,
    query: str,
    top_k: int | None = None,
    *,
    scope_customer_ids: list[str] | None = None,
    min_score: float | None = None,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> list[RetrievalHit]:
    if is_global_customer(customer_id):
        return search_knowledge_base_all(
            scope_customer_ids or [],
            query,
            top_k,
            min_score=min_score,
            embeddings=embeddings,
            vector_store=vector_store,
        )

    settings = get_settings()
    limit = clamp_top_k(top_k, settings.TOP_K_DEFAULT)
    global_limit = max(1, limit // 2)
    customer_limit = limit

    global_hits = search_knowledge_base(
        GLOBAL_CUSTOMER_ID,
        query,
        global_limit,
        min_score=min_score,
        embeddings=embeddings,
        vector_store=vector_store,
    )
    customer_hits = search_knowledge_base(
        customer_id,
        query,
        customer_limit,
        min_score=min_score,
        embeddings=embeddings,
        vector_store=vector_store,
    )

    merged: dict[tuple[str, int], RetrievalHit] = {}
    for hit in global_hits + customer_hits:
        key = (hit.document_id, hit.chunk_index)
        existing = merged.get(key)
        if existing is None or hit.score > existing.score:
            merged[key] = hit

    ordered = sorted(merged.values(), key=lambda item: item.score, reverse=True)
    return ordered[:limit]


def search_knowledge_base_all(
    customer_ids: list[str],
    query: str,
    top_k: int | None = None,
    *,
    min_score: float | None = None,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> list[RetrievalHit]:
    settings = get_settings()
    limit = clamp_top_k(top_k, settings.TOP_K_DEFAULT)
    per_collection_limit = max(2, min(3, limit))
    search_ids = [GLOBAL_CUSTOMER_ID]
    for customer_id in customer_ids:
        if customer_id != GLOBAL_CUSTOMER_ID and customer_id not in search_ids:
            search_ids.append(customer_id)

    merged: dict[tuple[str, int], RetrievalHit] = {}
    for customer_id in search_ids:
        for hit in search_knowledge_base(
            customer_id,
            query,
            per_collection_limit,
            min_score=min_score,
            embeddings=embeddings,
            vector_store=vector_store,
        ):
            key = (hit.document_id, hit.chunk_index)
            existing = merged.get(key)
            if existing is None or hit.score > existing.score:
                merged[key] = hit

    ordered = sorted(merged.values(), key=lambda item: item.score, reverse=True)
    return ordered[:limit]


def _filter_hits(raw_hits: list[SearchHit], min_score: float) -> list[RetrievalHit]:
    hits: list[RetrievalHit] = []
    for item in raw_hits:
        if item.score < min_score:
            continue
        payload = item.payload
        hits.append(
            RetrievalHit(
                document_id=str(payload.get("document_id", "")),
                title=str(payload.get("title", "Unbekannt")),
                chunk_index=int(payload.get("chunk_index", 0)),
                text=str(payload.get("text", "")),
                score=float(item.score),
            )
        )
    return hits


def format_hits_for_model(hits: list[RetrievalHit], start_index: int = 1) -> str:
    if not hits:
        return NO_HITS_TEXT

    parts: list[str] = [
        "Treffer aus der Wissensdatenbank (nicht alle müssen zitiert werden — nur genutzte Inhalte):"
    ]
    for offset, hit in enumerate(hits):
        number = start_index + offset
        parts.append(
            f'[{number}] Quelle: "{hit.title}" · Abschnitt {hit.chunk_index}\n{hit.text}'
        )
    return "\n\n".join(parts)


class SourceRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, int], RetrievalHit] = {}
        self._order: list[tuple[str, int]] = []

    def register(self, hits: list[RetrievalHit]) -> None:
        for hit in hits:
            key = (hit.document_id, hit.chunk_index)
            if key not in self._items:
                self._items[key] = hit
                self._order.append(key)

    @property
    def has_hits(self) -> bool:
        return bool(self._order)

    def ordered_sources(self) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for index, key in enumerate(self._order, start=1):
            hit = self._items[key]
            sources.append(
                {
                    "n": index,
                    "document_id": hit.document_id,
                    "title": hit.title,
                    "chunk_index": hit.chunk_index,
                    "score": round(hit.score, 4),
                }
            )
        return sources


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def filter_sources_by_answer_citations(
    sources: list[dict[str, Any]],
    answer: str,
) -> list[dict[str, Any]]:
    """Return only sources the model actually cited in the answer text."""
    if not sources:
        return []

    cited_numbers = []
    seen: set[int] = set()
    for match in _CITATION_PATTERN.finditer(answer):
        number = int(match.group(1))
        if number not in seen:
            seen.add(number)
            cited_numbers.append(number)

    if cited_numbers:
        cited_set = set(cited_numbers)
        return [source for source in sources if source["n"] in cited_set]

    # Model forgot explicit citations: show only the strongest single hit.
    return [max(sources, key=lambda item: item.get("score", 0))]
