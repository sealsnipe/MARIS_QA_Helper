# `backend/app/duplicates.py`

**Quellpfad:** `backend/app/duplicates.py`

## Zweck und logischer Aufbau

Stufe-1 Duplikat-Erkennung (exakter Content-Hash) vor Ingestion. Wird von `upload.py` (`find_duplicate_document`) und `document_fingerprints.py` (Stufe 2) genutzt. Liefert Payload für UI-Warnung + `allow_duplicate`-Bypass.

Kurz: Hash-basiertes Lookup in `documents` (pro customer, non-deleted) via `content_sha256`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.content_hash.content_sha256_from_text`
  - `app.models.Document`
  - SQLAlchemy `select`
- **Wird genutzt von:** `app.upload` (vor `ingest_text`), `app/document_fingerprints` (Kombi-Checks)
- **HTTP / UI:** Upload-Inspect + Upload mit `allow_duplicate`; Duplikat-Warnung in KB/Admin.
- **Daten:** SQLite `documents` (customer_id, content_sha256, deleted_at IS NULL)

## Konstanten, Typen und Modulebene

Keine Modulebene-Konstanten (Logik rein funktional).

## Funktionen und Klassen

### `duplicate_document_payload(document: Document) -> dict[str, str]`

**Beschreibung:** Erzeugt minimalen Payload für Duplikat-Fehler/UI (id, title, created_at).

**Parameter / Rückgabe:** Document-Row → dict mit 3 Feldern.

**Aufrufer / Aufgerufene:** `upload.ingest_combined` (bei Treffer), `find_duplicate...`.

### `find_duplicate_document(db: Session, customer_id: str, text: str, *, exclude_document_id: str | None = None) -> Document | None`

**Beschreibung:** Berechnet SHA256 des Textes; sucht exaktes Duplikat im Kunden-Scope (non-deleted). Optional Exclude für Re-Index/Update.

**Parameter / Rückgabe:** db, customer_id, text; exclude optional. Gibt erste matchende Document-Row oder None.

**Ablauf / lokale Variablen:** `digest = content_sha256_from_text(text)`; select mit where customer + sha + deleted_at null (+ != exclude).

**Aufrufer / Aufgerufene:** `upload.py` (vor ingest, mit combined), Duplikat-Checks in Admin/KB.
