# `backend/app/qdrant_store.py`

**Quellpfad:** `backend/app/qdrant_store.py`

## Zweck und logischer Aufbau

**Vektorstore-Abstraktion** für Qdrant: Protocol `VectorStore`, Produktionsimplementierung `QdrantVectorStore`, In-Memory-Testdouble `InMemoryVectorStore` und Singleton-Zugriff `get_vector_store()`.

Lesereihenfolge: `SearchHit` → `VectorStore` (Protocol) → `QdrantVectorStore` (mit `_name`, CRUD, Collection-Migration) → `InMemoryVectorStore` → Modul-Singleton.

Collection-Namen werden über `app.customers.collection_name` mit konfigurierbarem Prefix gebildet. Im Ingestion-Fluss: `ensure_collection` → `upsert`; im Retrieval: `search`; beim Löschen: `delete_document`. Mandanten-Umbenennung nutzt `copy_collection` + `delete_collection`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.config.get_settings`, `app.customers.collection_name`, `qdrant_client.QdrantClient`, `qdrant_client.http.models`
- **Wird genutzt von:** `backend/app/ingestion.py`, `backend/app/retrieval.py`, `backend/app/customers.py` (Collection-Rename/Copy), `backend/app/tests/conftest.py` (`InMemoryVectorStore`, `set_vector_store`), `test_admin_customers.py`
- **HTTP / UI / CLI:** Qdrant HTTP-API über `QDRANT_URL`; keine direkten FastAPI-Routen
- **Daten:** Qdrant-Collections pro Kunde (`{COLLECTION_PREFIX}{customer_id}`); Payload-Felder u. a. `customer_id`, `document_id`, `chunk_id`, `text`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `SearchHit` | Dataclass | Suchtreffer mit `score` und `payload` |
| `VectorStore` | Protocol | Vertrag für Collection-Lifecycle, Upsert, Search, Delete, Copy/Rename |
| `_vector_store` | Modul-Variable | Singleton-Cache (`VectorStore \| None`) |

## Funktionen und Klassen

### `SearchHit` (Dataclass)

| Feld | Typ | Beschreibung |
|---|---|---|
| `score` | `float` | Ähnlichkeits-Score (Cosine) |
| `payload` | `dict[str, Any]` | Metadaten inkl. Chunk-Text |

---

### `QdrantVectorStore`

**Beschreibung:** Produktions-Backend gegen Qdrant-Server.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `_client` | `QdrantClient` | Qdrant-HTTP-Client |
| `_collection_prefix` | `str` | Prefix für Collection-Namen |
| `_vector_dim` | `int` | Erwartete Vektorgröße |

---

### `QdrantVectorStore.__init__(url: str, collection_prefix: str, vector_dim: int) -> None`

**Beschreibung:** Initialisiert Client und Konfiguration.

**Aufrufer / Aufgerufene:** Instanziiert von `get_vector_store()`.

---

### `QdrantVectorStore._name(customer_id: str) -> str`

**Beschreibung:** Bildet Qdrant-Collection-Namen via `collection_name(customer_id, prefix=self._collection_prefix)`.

**Aufrufer / Aufgerufene:** Intern in allen Collection-Operationen.

---

### `QdrantVectorStore.ensure_collection(customer_id: str) -> None`

**Beschreibung:** Legt Collection an falls fehlend; prüft bei existierender Collection die Vektor-Dimension.

**Ablauf / lokale Variablen:** `name` — Collection-Name; `existing_dim` — aus Collection-Info; bei Mismatch `RuntimeError("vector_store_dim_mismatch")`.

**Aufrufer / Aufgerufene:** Aufgerufen von `upsert`, `copy_collection`; ruft `create_collection` mit Cosine-Distance.

---

### `QdrantVectorStore.upsert(customer_id: str, points: list[tuple[str, list[float], dict[str, Any]]]) -> None`

**Beschreibung:** Schreibt Punkte `(point_id, vector, payload)` in die Kunden-Collection.

**Parameter / Rückgabe:** Leere `points` → no-op; sonst `ensure_collection` dann `client.upsert`.

**Ablauf / lokale Variablen:** `qdrant_points` — Liste `PointStruct`.

**Aufrufer / Aufgerufene:** Aufgerufen von `ingestion.ingest_text`.

---

### `QdrantVectorStore.search(customer_id: str, query_vector: list[float], top_k: int) -> list[SearchHit]`

**Beschreibung:** Ähnlichkeitssuche; leere Liste wenn Collection nicht existiert.

**Ablauf / lokale Variablen:** `results` — `query_points`-Antwort; `hits` — normalisierte `SearchHit`-Liste.

**Aufrufer / Aufgerufene:** Aufgerufen von `retrieval.py`.

---

### `QdrantVectorStore.delete_document(customer_id: str, document_id: str) -> None`

**Beschreibung:** Löscht alle Punkte mit Payload `document_id == document_id`.

**Ablauf / lokale Variablen:** Filter auf `FieldCondition` mit `MatchValue`.

**Aufrufer / Aufgerufene:** Aufgerufen von `ingestion.delete_document`, Rollback in `ingest_text`.

---

### `QdrantVectorStore.copy_collection(old_customer_id: str, new_customer_id: str) -> None`

**Beschreibung:** Kopiert alle Punkte von alter in neue Collection; aktualisiert `customer_id` im Payload.

**Ablauf / lokale Variablen:** `offset`/`batch_size=256` — Scroll-Pagination; `new_points` — umgeschriebene Punkte; bei fehlender Quell-Collection: leere Ziel-Collection.

**Aufrufer / Aufgerufene:** Aufgerufen von `rename_collection`, `customers.py` bei Mandanten-ID-Wechsel.

---

### `QdrantVectorStore.delete_collection(customer_id: str) -> None`

**Beschreibung:** Entfernt gesamte Kunden-Collection falls vorhanden.

**Aufrufer / Aufgerufene:** Aufgerufen von `rename_collection`, Kunden-Löschung.

---

### `QdrantVectorStore.rename_collection(old_customer_id: str, new_customer_id: str) -> None`

**Beschreibung:** Copy-then-delete: `copy_collection` gefolgt von `delete_collection` der alten Collection.

**Aufrufer / Aufgerufene:** Aufgerufen bei Mandanten-Umbenennung in `customers.py`.

---

### `InMemoryVectorStore`

**Beschreibung:** Test-Double: Dict pro Collection-Name, Cosine-Suche in Python.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `vector_dim` | `int` | Erwartete Vektorlänge |
| `collections` | `dict[str, dict[str, tuple[list[float], dict]]]` | Collection → point_id → (vector, payload) |

---

### `InMemoryVectorStore.ensure_collection(customer_id: str) -> None`

**Beschreibung:** Legt leeren Bucket an via `setdefault`.

**Aufrufer / Aufgerufene:** Tests via `conftest.py`.

---

### `InMemoryVectorStore.upsert(customer_id: str, points: ...) -> None`

**Beschreibung:** Speichert Punkte im Memory-Bucket; prüft Vektor-Dimension.

**Aufrufer / Aufgerufene:** Test-Ingestion; wirft `RuntimeError("embedding_dim_mismatch")` bei falscher Länge.

---

### `InMemoryVectorStore.search(customer_id: str, query_vector: list[float], top_k: int) -> list[SearchHit]`

**Beschreibung:** Cosine-Ähnlichkeit über alle Punkte, sortiert absteigend, Top-K.

**Ablauf / lokale Variablen:** Nested `cosine(a, b)` — Dot-Product / Normen; `scored` — sortierte Treffer.

**Aufrufer / Aufgerufene:** Test-Retrieval.

---

### `InMemoryVectorStore.delete_document(customer_id: str, document_id: str) -> None`

**Beschreibung:** Entfernt Punkte deren Payload-`document_id` übereinstimmt.

**Aufrufer / Aufgerufene:** Test-Delete-Flow.

---

### `InMemoryVectorStore.copy_collection(old_customer_id: str, new_customer_id: str) -> None`

**Beschreibung:** Dupliziert die Daten in neue Collection (ohne pop der Quelle) — jetzt semantisch identisch zu Qdrant-Prod-`copy_collection` (F7 Fix). Payloads bekommen aktualisiertes `customer_id`. Quelle bleibt erhalten (Rename-Caller macht explizites delete danach).

**Aufrufer / Aufgerufene:** Tests für Mandanten-Migration (in `customers.py` + Admin-Tests).

---

### `InMemoryVectorStore.delete_collection(customer_id: str) -> None`

**Beschreibung:** Entfernt Collection-Key aus `collections`.

---

### `InMemoryVectorStore.rename_collection(old_customer_id: str, new_customer_id: str) -> None`

**Beschreibung:** Delegiert an `copy_collection` (alte Collection wird dort entfernt).

---

### `get_vector_store() -> VectorStore`

**Beschreibung:** Lazy Singleton mit `QdrantVectorStore` aus Settings (`QDRANT_URL`, `COLLECTION_PREFIX`, `EMBEDDING_DIM`).

**Aufrufer / Aufgerufene:** Aufgerufen von `ingestion.py`, `retrieval.py`, `customers.py`.

---

### `set_vector_store(store: VectorStore | None) -> None`

**Beschreibung:** Ersetzt Singleton (Tests injizieren `InMemoryVectorStore`).

**Aufrufer / Aufgerufene:** Aufgerufen von `conftest.py`.
