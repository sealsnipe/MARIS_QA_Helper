# 04 — Datenmodell

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

Zwei Speicher: **SQLite** (Nutzer, Kunden, Metadaten) und **Qdrant** (Vektoren, **Collection pro
Kunde**). Chunk-Text liegt **redundant** in Qdrant-Payload und SQLite. Jede Wissens-/Chat-Zeile
trägt `customer_id`.

---

## 1. SQLite-Schema

ORM: SQLAlchemy 2.x, `create_all` beim Start (kein Alembic im MVP). Zeitstempel ISO-8601 (UTC),
IDs UUIDv4-String.

### 1.1 `users`
```sql
CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,        -- lower-case gespeichert
  password_hash TEXT NOT NULL,               -- Argon2id-Encoded-String
  is_active     INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL
);
```

### 1.2 `customers`
```sql
CREATE TABLE customers (
  id         TEXT PRIMARY KEY,               -- slug, z.B. 'acme' (== customer_id)
  name       TEXT NOT NULL,                  -- Anzeigename, z.B. 'Acme GmbH'
  created_at TEXT NOT NULL
);
```
- `id` ist der **Slug** und zugleich `customer_id`; er bildet den Collection-Namen
  `kb_{id}`. Erlaubt: `[a-z0-9_-]+` (validieren — nie aus freiem Client-Input ableiten).

### 1.3 `user_customers` (n:m)
```sql
CREATE TABLE user_customers (
  user_id     TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  PRIMARY KEY (user_id, customer_id),
  FOREIGN KEY (user_id)     REFERENCES users(id),
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);
```
- Steuert, **welche** Kunden ein Nutzer sehen darf. Basis für `get_current_customer` (→ 403).

### 1.4 `documents`
```sql
CREATE TABLE documents (
  id                TEXT PRIMARY KEY,
  customer_id       TEXT NOT NULL,            -- Mandanten-Zugehörigkeit
  title             TEXT NOT NULL,
  source_type       TEXT NOT NULL DEFAULT 'manual', -- 'manual' | 'file' | später 'jira'
  source_url        TEXT,                     -- später (Jira-URL etc.)
  external_id       TEXT,                     -- später (Jira-Key etc.)
  original_filename TEXT,                     -- bei Upload
  mime_type         TEXT,                     -- bei Upload
  storage_path      TEXT,                     -- ./data/uploads/{customer_id}/{id}/{file}
  chunk_count       INTEGER NOT NULL DEFAULT 0,
  status            TEXT NOT NULL DEFAULT 'indexed', -- 'indexed' | 'failed'
  error_message     TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  deleted_at        TEXT,                     -- Soft-Delete; NULL = aktiv
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);
```
- Listen/Suche filtern **immer** `customer_id = :active AND deleted_at IS NULL`.
- `source_type='manual'` (Text) bzw. `'file'` (Upload). `source_url/external_id` für spätere Quellen.

### 1.5 `chunks`
```sql
CREATE TABLE chunks (
  id              TEXT PRIMARY KEY,           -- == Qdrant point id
  document_id     TEXT NOT NULL,
  customer_id     TEXT NOT NULL,              -- redundant für einfaches Scoping/Löschen
  chunk_index     INTEGER NOT NULL,
  text            TEXT NOT NULL,
  token_estimate  INTEGER,
  qdrant_point_id TEXT NOT NULL,              -- == id
  created_at      TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);
```
- `chunks.id == qdrant_point_id`: gemeinsamer UUID → gezieltes Löschen per Point-IDs.

### 1.6 Beziehungen
```text
users  n ── n customers      (über user_customers)   → Sichtbarkeit/Berechtigung
customers 1 ── n documents   (customer_id)            → Wissen gehört einem Kunden
documents 1 ── n chunks      (document_id, customer_id)
chunks ──────── Qdrant-Points in kb_{customer_id}     (über qdrant_point_id)
```

## 2. Qdrant-Schema

### 2.1 Collections — **eine pro Kunde**
- Name: `f"{COLLECTION_PREFIX}{customer_id}"`, Default-Prefix `kb_` → `kb_acme`, `kb_globex`.
- Vektorparameter: `size=1536`, `distance=COSINE`.
- **Lazy** per `ensure_collection(customer_id)` (idempotent) bei erster Ingestion.
- Suche gegen leere/nicht existierende Collection → **leere Trefferliste**, kein Fehler.
```python
def collection_name(customer_id: str) -> str:
    assert re.fullmatch(r"[a-z0-9_-]+", customer_id)   # nie roher Client-Input
    return f"{COLLECTION_PREFIX}{customer_id}"
```

### 2.2 Point-Payload
```json
{
  "customer_id": "acme",
  "document_id": "uuid",
  "chunk_id": "uuid",
  "chunk_index": 4,
  "title": "VPN Runbook",
  "source_type": "file",
  "source_url": null,
  "text": "Chunk-Text hier ..."
}
```
- `text` ist Pflicht (Agent/LLM braucht ihn direkt). `customer_id` als Defense-in-Depth.

### 2.3 Operationen (Vertrag, `qdrant_store.py`)
| Funktion | Zweck |
|---|---|
| `collection_name(customer_id)` | deterministischer, validierter Name |
| `ensure_collection(customer_id)` | idempotent anlegen (1536/Cosine) |
| `upsert(customer_id, points)` | Points in `kb_{cid}` schreiben |
| `search(customer_id, query_vector, top_k)` | Top-K + Score + Payload aus `kb_{cid}`; leer wenn keine Collection |
| `delete_document(customer_id, document_id)` | Points des Dokuments löschen (per Point-IDs) |

## 3. ID- & Konsistenz-Strategie
- IDs serverseitig als UUIDv4 (außer `customers.id` = Slug).
- Ingestion „best effort transaktional": bei Embedding-/Upsert-Fehler **kein** `indexed`-Doc;
  bei Datei-Extraktionsfehler `status='failed'`, **nichts** in Qdrant.
- Delete: erst Qdrant-Points, dann `deleted_at`.

## 4. Lebenszyklus (Beispiel, Kunde `acme`)
```text
Upload "vpn.pdf" (Kunde acme) → Loader extrahiert Text → 3 Chunks
  documents: 1 row (customer_id=acme, source_type=file, original_filename=vpn.pdf, status=indexed)
  chunks:    3 rows (customer_id=acme)
  qdrant:    3 points in kb_acme
Suche als Kunde globex → kb_globex → 0 Treffer (nie acme-Daten)   ← Isolation
delete document → kb_acme Points weg; documents.deleted_at gesetzt
```

## 5. Spätere Erweiterungen (vgl. `12`)
- `users.role` / feingranulare Rechte; `customers`-Admin-UI.
- `documents` Unique-Constraint `(customer_id, source_type, external_id)` für Jira-Dedup.
- `text_sha256` für Duplikaterkennung; Versionierung.
