# `backend/app/ingestion.py`

**Quellpfad:** `backend/app/ingestion.py`

## Zweck und logischer Aufbau

Zentrales Modul für die **Indizierung von Text** in die Wissensdatenbank. Es orchestriert Validierung, Chunking, Embedding-Erzeugung, Qdrant-Upsert und SQL-Persistenz (`Document`, `Chunk`). Zusätzlich bietet es Abfrage- und Soft-Delete-Funktionen für Dokumente pro Kunde.

Lesereihenfolge: Exception/Dataclass-Typen (`IngestionError`, `IngestResult`) → private Hilfsfunktionen (`_estimate_tokens`, `_document_to_dict`) → `ingest_text` (Kernpipeline) → Listen- und Löschfunktionen.

Ablauf bei `ingest_text`: Titel prüfen → Text normalisieren/validieren → in Chunks teilen → `Document`-Row anlegen (`source_text`) → embedden und indexieren → commit. Bei Embedding-Fehler nach `flush`: `db.rollback()` — kein persistiertes Document. Bei Qdrant-Fehler Rollback-Versuch per `vector_store.delete_document`, dann `IngestionError("vector_store_failed")`.

Bearbeiten: `get_document_text` liefert `source_text` oder rekonstruiert aus Chunks; `update_document_content` embeddet zuerst, löscht dann alte Vektoren/Chunks und re-indiziert (gleiche `document_id`).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.chunking` (`chunk_text`, `validate_ingest_text`), `app.embeddings` (`EmbeddingsBackend`, `get_embeddings_backend`), `app.models` (`Chunk`, `Document`, `utc_now_iso`), `app.qdrant_store` (`VectorStore`, `get_vector_store`), `sqlalchemy` (`select`, `Session`), `uuid`
- **Wird genutzt von:** `backend/app/routes.py` (API-Dokumente), `backend/app/upload.py` (`ingest_combined`), `backend/app/main.py` (`IngestionError`-Handler), `scripts/seed_kb.py`, Tests in `backend/app/tests/test_ingestion.py`
- **HTTP / UI / CLI:** Fehlercodes werden in `main.py` auf HTTP-Status gemappt (400/502); indirekt über Upload- und Dokument-Routen in `routes.py`
- **Daten:** SQLite-Tabellen `documents`, `chunks`; Qdrant-Collections pro Kunde (über `VectorStore`)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `IngestionError` | Exception-Klasse | Maschinenlesbarer Fehler mit `code` und optionalem `detail` |
| `IngestResult` | Dataclass | Ergebniscontainer mit persistiertem `Document` nach Indizierung |

## Funktionen und Klassen

### `IngestionError`

**Beschreibung:** Exception für alle Ingestion-Fehler mit stabilen Fehlercodes für API-Mapping.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `code` | `str` | z. B. `invalid_title`, `empty_text`, `embedding_failed`, `vector_store_failed` |
| `detail` | `str \| None` | Zusatzinformation (z. B. Exception-Text bei Embedding-Fehler) |

---

### `IngestionError.__init__(code: str, detail: str | None = None) -> None`

**Beschreibung:** Setzt `code` und `detail`; übergibt `code` als Exception-Message an `super().__init__`.

**Parameter / Rückgabe:** `code` — Fehlercode; `detail` — optionaler Detailtext.

**Aufrufer / Aufgerufene:** Geworfen in `ingest_text`; abgefangen in `backend/app/main.py` (`ingestion_error_handler`).

---

### `IngestResult` (Dataclass)

**Beschreibung:** Rückgabeobjekt nach erfolgreicher Indizierung.

| Feld | Typ | Beschreibung |
|---|---|---|
| `document` | `Document` | Frisch committetes ORM-Dokument inkl. `chunk_count` |

---

### `_estimate_tokens(text: str) -> int`

**Beschreibung:** Grobe Token-Schätzung für Chunk-Metadaten (Heuristik: 1 Token ≈ 4 Zeichen).

**Parameter / Rückgabe:** `text` — Chunk-Text; Rückgabe `max(1, len(text) // 4)`.

**Ablauf / lokale Variablen:** Keine nennenswerten Locals.

**Aufrufer / Aufgerufene:** Aufgerufen in `ingest_text` für `Chunk.token_estimate`.

---

### `_document_to_dict(document: Document) -> dict[str, Any]`

**Beschreibung:** Serialisiert ein `Document`-ORM-Objekt für API-Listen (ohne gelöschte Felder wie `deleted_at`).

**Parameter / Rückgabe:** `document` — SQLAlchemy-Instanz; Rückgabe Dict mit `id`, `customer_id`, `title`, `source_type`, `original_filename`, `mime_type`, `chunk_count`, `status`, `created_at`, `updated_at`.

**Aufrufer / Aufgerufene:** Aufgerufen von `list_documents`, `list_documents_for_customers`.

---

### `ingest_text(...) -> IngestResult`

**Beschreibung:** Hauptfunktion: Text validieren, chunken, embedden, in Qdrant und SQLite persistieren.

**Parameter / Rückgabe:**
- `db: Session` — SQLAlchemy-Session
- `customer_id: str` — Mandanten-ID
- `title: str` — Dokumenttitel (1–200 Zeichen nach Trim)
- `text: str` — Rohtext
- `source_type: str = "manual"` — Quelltyp
- Keyword-only: `document_id`, `original_filename`, `mime_type`, `storage_path`, `source_url`, `external_id` — optionale Metadaten
- `embeddings`, `vector_store` — injizierbare Backends (Default: Singletons)
- Rückgabe: `IngestResult` mit `status="indexed"`

**Ablauf / lokale Variablen:** `cleaned_title` — getrimmter Titel; `normalized` — via `validate_ingest_text`; `pieces` — Chunk-Liste; `vectors` — Embedding-Ergebnis; `points` — Tupel `(chunk_id, vector, payload)` für Qdrant; `chunk_rows` — ORM-`Chunk`-Instanzen; `now` — ISO-Zeitstempel; `document` — neues `Document`-Objekt.

**Aufrufer / Aufgerufene:** Aufgerufen von `upload.py`, `routes.py`, `seed_kb.py`, Tests; ruft `validate_ingest_text`, `chunk_text`, `embeddings.embed_documents`, `vector_store.ensure_collection/upsert/delete_document`, DB-Commit.

**Wirft:** `IngestionError` bei `invalid_title`, Validierungsfehlern aus `validate_ingest_text`, `empty_text`, `embedding_failed`, `vector_store_failed`. Bei `embedding_failed` nach `flush`: Transaction-Rollback, kein Document in DB.

---

### `get_document(db, customer_id, document_id) -> Document | None`

**Beschreibung:** Lädt ein nicht soft-gelöschtes Document, scoped auf `customer_id`.

---

### `get_document_text(db, customer_id, document_id) -> tuple[Document, str] | None`

**Beschreibung:** Liefert Document plus bearbeitbaren Text: bevorzugt `source_text`, sonst Rekonstruktion aus sortierten Chunks.

---

### `update_document_content(...) -> IngestResult`

**Beschreibung:** Admin-Bearbeitung: Titel/Text validieren, embedden, alte Qdrant-Points und Chunk-Rows entfernen, neu indexieren, `source_text` setzen. Datei-Ursprung → `source_type = "manual"` (Originaldatei bleibt archiviert).

**Wirft:** `IngestionError("not_found")` bei falschem Mandanten/Dokument.

---

### `list_documents_for_customers(db: Session, customer_ids: list[str]) -> list[dict[str, Any]]`

**Beschreibung:** Listet nicht soft-gelöschte Dokumente für mehrere Kunden, absteigend nach `created_at`.

**Parameter / Rückgabe:** `db`, `customer_ids`; leere `customer_ids` → leere Liste; sonst Liste von Dicts via `_document_to_dict`.

**Ablauf / lokale Variablen:** `stmt` — SQLAlchemy-Select mit `deleted_at.is_(None)`; `rows` — ORM-Ergebnisliste.

**Aufrufer / Aufgerufene:** Aufgerufen von `backend/app/routes.py` (Global-/Multi-Kunden-Ansicht).

---

### `list_documents(db: Session, customer_id: str) -> list[dict[str, Any]]`

**Beschreibung:** Listet Dokumente eines einzelnen Kunden (nicht soft-gelöscht).

**Parameter / Rückgabe:** `db`, `customer_id`; Rückgabe serialisierte Dokument-Dicts.

**Ablauf / lokale Variablen:** `stmt`, `rows` — analog zu `list_documents_for_customers`, gefiltert auf einen `customer_id`.

**Aufrufer / Aufgerufene:** Aufgerufen von `backend/app/routes.py`.

---

### `delete_document(db: Session, customer_id: str, document_id: str, *, vector_store: VectorStore | None = None) -> bool`

**Beschreibung:** Soft-Delete: entfernt Vektoren aus Qdrant und setzt `deleted_at` in SQLite.

**Parameter / Rückgabe:** `db`, `customer_id`, `document_id`, optional `vector_store`; `False` wenn Dokument fehlt, bereits gelöscht oder falscher Kunde; sonst `True`.

**Ablauf / lokale Variablen:** `document` — per `db.get`; `store` — `vector_store` oder `get_vector_store()`.

**Aufrufer / Aufgerufene:** Aufgerufen von `routes.py`, Tests; ruft `store.delete_document`, setzt `deleted_at`/`updated_at`, `db.commit`.
