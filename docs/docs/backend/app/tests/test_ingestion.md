# `backend/app/tests/test_ingestion.py`

**Quellpfad:** `backend/app/tests/test_ingestion.py`

## Zweck und logischer Aufbau

Direkte Tests der **Ingestion-Schicht** (`ingest_text`, `get_document_text`, `update_document_content`, `list_documents`, `delete_document`) gegen SQLite und den gemockten In-Memory-Vektorstore. Abgedeckt sind Erfolgsfall, leerer/zu kurzer Text, Embedding-Fehler ohne persistiertes Document, Admin-Bearbeiten/Re-Index und mandantenscharfes Löschen.

Die Tests nutzen `create_customer` aus Conftest und übergeben `fake_embeddings` / `fake_vector_store` explizit an `ingest_text` — nicht den HTTP-API-Pfad.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.customers.collection_name`
  - `app.ingestion.IngestionError`, `delete_document`, `get_document_text`, `ingest_text`, `list_documents`, `update_document_content`
  - `app.tests.conftest.create_customer`
  - `pytest`
- **Wird genutzt von:** pytest
- **HTTP / UI:** keine
- **Daten:** SQLite `Customer`, `Document`, Chunks; Qdrant-Bucket `fake_vector_store.collections[collection_name(...)]`
- **Abgedecktes Modul:** `backend/app/ingestion.py`, `backend/app/chunking.py` (indirekt)

## Konstanten, Typen und Modulebene

Keine Modulebenen-Symbole; innere Klasse `BrokenEmbeddings` nur innerhalb eines Tests (siehe unten).

## Funktionen und Klassen

### `test_ingest_success_writes_sqlite_and_qdrant(db_session, fake_vector_store, fake_embeddings)`

**Beschreibung:** Erfolgreiche Text-Ingestion schreibt indexed Document in SQLite und Punkte in Qdrant.

**Parameter / Rückgabe:** `db_session`, `fake_vector_store`, `fake_embeddings`.

**Ablauf / lokale Variablen:** `text` — lang genug für Validierung; `result.document` — `status == "indexed"`, `chunk_count >= 1`; `docs` via `list_documents`; `bucket` — Anzahl Punkte = `chunk_count`.

**Aufrufer / Aufgerufene:** `ingest_text`, `list_documents`, `collection_name`.

---

### `test_ingest_rejects_empty_text(db_session, fake_vector_store, fake_embeddings)`

**Beschreibung:** Zu kurzer Text → `IngestionError` mit `code == "empty_text"`; keine Dokumente in Liste.

**Ablauf / lokale Variablen:** `exc` — `pytest.raises(IngestionError)`; `text="kurz"`.

---

### `test_embedding_failure_does_not_create_indexed_document(db_session, fake_vector_store)`

**Beschreibung:** Embedding-Backend wirft → `IngestionError` `embedding_failed`; DB-Liste leer.

**Parameter / Rückgabe:** Kein `fake_embeddings`-Fixture; lokales `BrokenEmbeddings`.

**Ablauf / lokale Variablen:**
- **`BrokenEmbeddings`** (innere Klasse): `embed_documents` / `embed_query` werfen `RuntimeError("boom")`
- `ingest_text` mit `BrokenEmbeddings()`; Assertion `exc.value.code == "embedding_failed"`

**Aufrufer / Aufgerufene:** `ingest_text` Fehlerpfad in `ingestion.py`.

---

### `test_delete_document_scoped_to_customer(db_session, fake_vector_store, fake_embeddings)`

**Beschreibung:** Löschen mit falscher `customer_id` schlägt fehl (`False`); mit korrekter ID `True` und leere Liste.

**Ablauf / lokale Variablen:** `acme_doc` — ingest unter `bg-ludwigshafen`; `delete_document` für `kkrr` → `False`, für `bg-ludwigshafen` → `True`.

**Aufrufer / Aufgerufene:** `delete_document`, `ingest_text`, `list_documents`.

---

### `test_get_document_text_uses_source_text(...)`

**Beschreibung:** `get_document_text` liefert gespeichertes `source_text` nach Ingest.

---

### `test_update_document_content_reindexes(...)`

**Beschreibung:** PUT-Logik auf Ingestion-Ebene: Titel/Text ändern, Chunk-Anzahl/Re-Index, `source_text` aktualisiert.

---

### `test_update_document_wrong_customer_raises_not_found(...)`

**Beschreibung:** `update_document_content` mit falscher `customer_id` → `IngestionError("not_found")`.

## (Optional) Tests

- **Fixtures:** `db_session`, `fake_vector_store`, `fake_embeddings` (je nach Test); autouse-Mocks parallel aktiv. Helfer: `create_customer`.
- **Abgedecktes Modul:** `backend/app/ingestion.py`, `backend/app/customers.py`, `backend/app/qdrant_store.py`.

| Test | Intent |
|---|---|
| `test_ingest_success_writes_sqlite_and_qdrant` | Erfolg: SQLite + Qdrant befüllt |
| `test_ingest_rejects_empty_text` | `empty_text` bei kurzem Text |
| `test_embedding_failure_does_not_create_indexed_document` | `embedding_failed`, kein indexed Doc |
| `test_delete_document_scoped_to_customer` | Delete nur im eigenen Mandanten |
| `test_get_document_text_uses_source_text` | `source_text` nach Ingest lesbar |
| `test_update_document_content_reindexes` | Bearbeiten triggert Re-Index |
| `test_update_document_wrong_customer_raises_not_found` | Mandanten-Check bei Update |
