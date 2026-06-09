from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.customers import collection_name


@dataclass
class SearchHit:
    score: float
    payload: dict[str, Any]


class VectorStore(Protocol):
    def ensure_collection(self, customer_id: str) -> None: ...

    def upsert(
        self,
        customer_id: str,
        points: list[tuple[str, list[float], dict[str, Any]]],
    ) -> None: ...

    def search(self, customer_id: str, query_vector: list[float], top_k: int) -> list[SearchHit]: ...

    def search_fingerprints(
        self, customer_id: str, query_vector: list[float], top_k: int
    ) -> list[SearchHit]: ...

    def delete_document(self, customer_id: str, document_id: str) -> None: ...

    def copy_collection(self, old_customer_id: str, new_customer_id: str) -> None: ...
    def delete_collection(self, customer_id: str) -> None: ...
    def rename_collection(self, old_customer_id: str, new_customer_id: str) -> None: ...


class QdrantVectorStore:
    def __init__(self, url: str, collection_prefix: str, vector_dim: int) -> None:
        self._client = QdrantClient(url=url)
        self._collection_prefix = collection_prefix
        self._vector_dim = vector_dim

    def _name(self, customer_id: str) -> str:
        return collection_name(customer_id, prefix=self._collection_prefix)

    def ensure_collection(self, customer_id: str) -> None:
        name = self._name(customer_id)
        if self._client.collection_exists(name):
            info = self._client.get_collection(name)
            existing_dim = info.config.params.vectors.size  # type: ignore[union-attr]
            if existing_dim != self._vector_dim:
                raise RuntimeError("vector_store_dim_mismatch")
            return

        self._client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(size=self._vector_dim, distance=qmodels.Distance.COSINE),
        )

    def upsert(
        self,
        customer_id: str,
        points: list[tuple[str, list[float], dict[str, Any]]],
    ) -> None:
        if not points:
            return
        self.ensure_collection(customer_id)
        qdrant_points = [
            qmodels.PointStruct(id=point_id, vector=vector, payload=payload)
            for point_id, vector, payload in points
        ]
        self._client.upsert(collection_name=self._name(customer_id), points=qdrant_points)

    def search(self, customer_id: str, query_vector: list[float], top_k: int) -> list[SearchHit]:
        name = self._name(customer_id)
        if not self._client.collection_exists(name):
            return []

        results = self._client.query_points(
            collection_name=name,
            query=query_vector,
            limit=top_k,
            query_filter=qmodels.Filter(
                must_not=[
                    qmodels.FieldCondition(
                        key="kind",
                        match=qmodels.MatchValue(value="document_fingerprint"),
                    )
                ]
            ),
            with_payload=True,
        ).points
        hits: list[SearchHit] = []
        for item in results:
            payload = dict(item.payload or {})
            hits.append(SearchHit(score=float(item.score or 0.0), payload=payload))
        return hits

    def search_fingerprints(
        self, customer_id: str, query_vector: list[float], top_k: int
    ) -> list[SearchHit]:
        name = self._name(customer_id)
        if not self._client.collection_exists(name):
            return []

        results = self._client.query_points(
            collection_name=name,
            query=query_vector,
            limit=top_k,
            query_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="kind",
                        match=qmodels.MatchValue(value="document_fingerprint"),
                    )
                ]
            ),
            with_payload=True,
        ).points
        hits: list[SearchHit] = []
        for item in results:
            payload = dict(item.payload or {})
            hits.append(SearchHit(score=float(item.score or 0.0), payload=payload))
        return hits

    def delete_document(self, customer_id: str, document_id: str) -> None:
        name = self._name(customer_id)
        if not self._client.collection_exists(name):
            return
        self._client.delete(
            collection_name=name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def copy_collection(self, old_customer_id: str, new_customer_id: str) -> None:
        old_name = self._name(old_customer_id)
        new_name = self._name(new_customer_id)
        if not self._client.collection_exists(old_name):
            # ensure target exists empty (for consistency)
            self.ensure_collection(new_customer_id)
            return
        if self._client.collection_exists(new_name):
            # cleanup stale from previous partial rename
            self._client.delete_collection(new_name)
        # we know our dim; recreate with same params as we use everywhere
        self._client.create_collection(
            collection_name=new_name,
            vectors_config=qmodels.VectorParams(size=self._vector_dim, distance=qmodels.Distance.COSINE),
        )
        offset: Any = None
        batch_size = 256
        while True:
            records, next_offset = self._client.scroll(
                collection_name=old_name,
                offset=offset,
                limit=batch_size,
                with_payload=True,
                with_vectors=True,
            )
            if not records:
                break
            new_points: list[qmodels.PointStruct] = []
            for rec in records:
                payload = dict(rec.payload or {})
                payload["customer_id"] = new_customer_id
                vec = rec.vector
                if isinstance(vec, dict):
                    # named vectors; take first (we use single unnamed)
                    vec = next(iter(vec.values())) if vec else []
                new_points.append(
                    qmodels.PointStruct(id=rec.id, vector=vec, payload=payload)
                )
            if new_points:
                self._client.upsert(collection_name=new_name, points=new_points)
            offset = next_offset
            if offset is None:
                break

    def delete_collection(self, customer_id: str) -> None:
        name = self._name(customer_id)
        if self._client.collection_exists(name):
            self._client.delete_collection(name)

    def rename_collection(self, old_customer_id: str, new_customer_id: str) -> None:
        self.copy_collection(old_customer_id, new_customer_id)
        self.delete_collection(old_customer_id)


class InMemoryVectorStore:
    """Test double: separate dict per collection."""

    def __init__(self, vector_dim: int) -> None:
        self.vector_dim = vector_dim
        self.collections: dict[str, dict[str, tuple[list[float], dict[str, Any]]]] = {}

    def ensure_collection(self, customer_id: str) -> None:
        name = collection_name(customer_id)
        self.collections.setdefault(name, {})

    def upsert(
        self,
        customer_id: str,
        points: list[tuple[str, list[float], dict[str, Any]]],
    ) -> None:
        bucket = self.collections.setdefault(collection_name(customer_id), {})
        for point_id, vector, payload in points:
            if len(vector) != self.vector_dim:
                raise RuntimeError("embedding_dim_mismatch")
            bucket[point_id] = (vector, payload)

    def search(self, customer_id: str, query_vector: list[float], top_k: int) -> list[SearchHit]:
        bucket = self.collections.get(collection_name(customer_id), {})
        if not bucket:
            return []

        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b, strict=True))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = [
            SearchHit(score=cosine(query_vector, vector), payload=payload)
            for vector, payload in bucket.values()
            if payload.get("kind") != "document_fingerprint"
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]

    def search_fingerprints(
        self, customer_id: str, query_vector: list[float], top_k: int
    ) -> list[SearchHit]:
        bucket = self.collections.get(collection_name(customer_id), {})
        if not bucket:
            return []

        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b, strict=True))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(y * y for y in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = [
            SearchHit(score=cosine(query_vector, vector), payload=payload)
            for vector, payload in bucket.values()
            if payload.get("kind") == "document_fingerprint"
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]

    def delete_document(self, customer_id: str, document_id: str) -> None:
        bucket = self.collections.get(collection_name(customer_id), {})
        for point_id, (_, payload) in list(bucket.items()):
            if payload.get("document_id") == document_id:
                del bucket[point_id]

    def copy_collection(self, old_customer_id: str, new_customer_id: str) -> None:
        """Copy (duplicate) data to new collection; leave source intact.
        Matches QdrantVectorStore semantics (prod). The pop/move behavior was
        the InMemory-only deviation noted in reviews.
        """
        old_name = collection_name(old_customer_id)
        new_name = collection_name(new_customer_id)
        if old_name not in self.collections:
            self.collections.setdefault(new_name, {})
            return
        if new_name in self.collections:
            del self.collections[new_name]
        old_bucket = self.collections.get(old_name, {})
        new_bucket: dict[str, tuple[list[float], dict[str, Any]]] = {}
        for pid, (vec, payload) in list(old_bucket.items()):
            p = dict(payload or {})
            p["customer_id"] = new_customer_id
            new_bucket[pid] = (vec, p)
        self.collections[new_name] = new_bucket
        # NOTE: old collection remains (caller of rename does explicit delete after SQLite step)

    def delete_collection(self, customer_id: str) -> None:
        name = collection_name(customer_id)
        self.collections.pop(name, None)

    def rename_collection(self, old_customer_id: str, new_customer_id: str) -> None:
        self.copy_collection(old_customer_id, new_customer_id)
        # old removed inside copy


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        settings = get_settings()
        _vector_store = QdrantVectorStore(
            url=settings.QDRANT_URL,
            collection_prefix=settings.COLLECTION_PREFIX,
            vector_dim=settings.EMBEDDING_DIM,
        )
    return _vector_store


def set_vector_store(store: VectorStore | None) -> None:
    global _vector_store
    _vector_store = store
