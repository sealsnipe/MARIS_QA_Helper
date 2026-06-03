# `backend/app/embeddings.py`

**Quellpfad:** `backend/app/embeddings.py`

## Zweck und logischer Aufbau

Abstraktionsschicht für **Text-Embeddings** im RAG-Pipeline. Das Modul definiert ein Protocol für Embedding-Backends, eine OpenAI-kompatible Implementierung und einen lazy initialisierten Singleton-Zugriff über `get_embeddings_backend()`.

Lesereihenfolge: `EmbeddingsBackend` (Protocol) → `OpenAIEmbeddings` (Dataclass mit API-Client) → Modul-Singleton `_embeddings_backend` → Fabrik- und Test-Helfer `get_embeddings_backend` / `set_embeddings_backend`.

Im Datenfluss werden Embeddings bei **Ingestion** (`ingest_text`) für Dokument-Chunks und bei **Retrieval** (`search_knowledge_base`) für die Query-Vektorisierung erzeugt. Die erwartete Vektordimension kommt aus den Settings und muss mit Qdrant-Collection und Modell übereinstimmen.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.config.get_settings`, `openai.OpenAI`, `typing.Protocol`, `dataclasses.dataclass`
- **Wird genutzt von:** `backend/app/ingestion.py` (`EmbeddingsBackend`, `get_embeddings_backend`), `backend/app/retrieval.py` (gleiche Symbole), `backend/app/tests/conftest.py` (`set_embeddings_backend` für Test-Doubles)
- **HTTP / UI / CLI:** keine direkten Endpoints — indirekt über Ingestion- und Chat-APIs
- **Daten:** keine DB-Tabellen; Vektoren landen in Qdrant über `app.qdrant_store`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `EmbeddingsBackend` | Protocol | Vertrag: `embed_documents(texts)` und `embed_query(text)` liefern Float-Vektoren |
| `_embeddings_backend` | Modul-Variable | Singleton-Cache (`EmbeddingsBackend \| None`), initial `None` |

## Funktionen und Klassen

### `OpenAIEmbeddings` (Dataclass)

**Beschreibung:** OpenAI-kompatibler Embedding-Client mit Dimensionsprüfung nach jedem API-Aufruf.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `api_key` | `str` | API-Schlüssel für OpenAI-kompatible Endpoints |
| `base_url` | `str` | Basis-URL des Embedding-Dienstes |
| `model` | `str` | Modellname (z. B. aus `EMBEDDING_MODEL`) |
| `expected_dim` | `int` | Erwartete Vektorlänge (aus `EMBEDDING_DIM`) |
| `_client` | `OpenAI` | Interner HTTP-Client, in `__post_init__` gesetzt |

---

### `OpenAIEmbeddings.__post_init__() -> None`

**Beschreibung:** Initialisiert `self._client` mit `api_key` und `base_url`.

**Parameter / Rückgabe:** Keine Parameter; kein Rückgabewert.

**Ablauf / lokale Variablen:** Setzt `_client` via `OpenAI(...)`.

**Aufrufer / Aufgerufene:** Wird automatisch nach Dataclass-Erstellung aufgerufen; nutzt `OpenAI`.

---

### `OpenAIEmbeddings.embed_documents(texts: list[str]) -> list[list[float]]`

**Beschreibung:** Erzeugt Embedding-Vektoren für eine Liste von Texten in einem API-Call.

**Parameter / Rückgabe:** `texts` — Liste der zu embeddenden Strings; Rückgabe ist Liste gleichlanger Float-Listen. Leere Eingabe → leere Liste.

**Ablauf / lokale Variablen:** `response` — API-Antwort; `vectors` — extrahierte Embeddings aus `response.data`. Pro Vektor wird `len(vector)` gegen `expected_dim` geprüft; bei Abweichung `RuntimeError("embedding_dim_mismatch")`.

**Aufrufer / Aufgerufene:** Aufgerufen von `embed_query`, `backend/app/ingestion.py` (`ingest_text`), `backend/app/retrieval.py`; ruft `self._client.embeddings.create` auf.

---

### `OpenAIEmbeddings.embed_query(text: str) -> list[float]`

**Beschreibung:** Einzel-Query-Embedding; delegiert an `embed_documents([text])` und liefert den ersten Vektor.

**Parameter / Rückgabe:** `text` — Suchanfrage; Rückgabe ein Float-Vektor.

**Ablauf / lokale Variablen:** `vectors` — Ergebnis von `embed_documents`.

**Aufrufer / Aufgerufene:** Aufgerufen von `backend/app/retrieval.py`; ruft `embed_documents` auf.

---

### `get_embeddings_backend() -> EmbeddingsBackend`

**Beschreibung:** Liefert das globale Embedding-Backend; erzeugt bei erstem Aufruf `OpenAIEmbeddings` aus Settings.

**Parameter / Rückgabe:** Keine Parameter; Rückgabe `EmbeddingsBackend`.

**Ablauf / lokale Variablen:** `settings` — via `get_settings()`; Felder `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`.

**Aufrufer / Aufgerufene:** Aufgerufen von `ingestion.py`, `retrieval.py`; ruft `get_settings`, instanziiert `OpenAIEmbeddings`.

---

### `set_embeddings_backend(backend: EmbeddingsBackend | None) -> None`

**Beschreibung:** Setzt oder ersetzt den Singleton (Tests injizieren Mock-Backends).

**Parameter / Rückgabe:** `backend` — neues Backend oder `None` zum Zurücksetzen; kein Rückgabewert.

**Ablauf / lokale Variablen:** Schreibt globale `_embeddings_backend`.

**Aufrufer / Aufgerufene:** Aufgerufen von `backend/app/tests/conftest.py` (Fixtures).
