# 08 — Datenmodell-Synchronisation

**Stand:** 2026-06-03

---

## Drei Speicher

| Store | Inhalt | Identifier |
|---|---|---|
| **SQLite** | Users, Customers, Memberships, Documents, Chunks, Chats, Prompts | `customer_id` Slug als FK |
| **Qdrant** | Embeddings + Payload pro Chunk | Collection `kb_{customer_id}` |
| **Dateisystem** | Original-Uploads | `./data/uploads/{customer_id}/{document_id}/` |

---

## Document-Lebenszyklus

```text
ingest_text
  → SQLite: documents (status=indexed) + chunks (qdrant_point_id)
  → Qdrant: points mit payload { customer_id, document_id, chunk_id, text, … }

delete_document
  → Qdrant: filter document_id
  → SQLite: deleted_at
  → FS: Upload-Ordner bleibt (kein Hard-Delete im MVP)
```

---

## Slug-Rename — Konsistenz

| System | Aktion |
|---|---|
| SQLite | Neue PK-Zeile `customers`, UPDATE aller FK-Tabellen, alte Zeile löschen |
| Qdrant | copy → delete old collection |
| Uploads | `shutil.move` Ordner (Warnung bei Fehler, KB bleibt konsistent) |
| Chats | `chat_sessions.customer_id` updated |
| Prompts | Scope-Key = Slug; Zeile migrieren |

Teilfehler Qdrant vor SQLite-Commit: Retry möglich nach Cleanup der Ziel-Collection.

Spiegel: `customers.md` (`rename_tenant_customer`), `08` → `docs/04_data_model.md`

---

## Embedding-Dimension

`EMBEDDING_DIM` muss zur Qdrant-Collection passen. Wechsel des Embedding-Modells → Collections neu aufbauen (Re-Ingest).

---

## Betroffene Spiegel-Dateien

`models.md`, `db.md`, `ingestion.md`, `qdrant_store.md`, `customers.md`, `upload.md`, `docs/04_data_model.md`
