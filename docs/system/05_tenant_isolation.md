# 05 — Mandanten-Isolation (Tenant)

**Stand:** 2026-06-03 · **Invariante:** Kein Nutzer darf fremde Mandantendaten sehen oder schreiben.

---

## Enforcement-Matrix

| Schicht | Mechanismus | Datei |
|---|---|---|
| **Session** | `customer_id` nur serverseitig gesetzt | `routes.py`, `auth.py` |
| **Membership** | `user_customers` + `user_has_customer()` | `customers.py` |
| **Route Depends** | `get_current_customer` — leert Session bei Invalidität | `tenant.py` |
| **Chat** | `get_session_for_user(user, customer)` | `chats.py` |
| **Dokumente** | `document.customer_id == active customer` | `ingestion.py`, `routes.py` |
| **Qdrant** | Separate Collection `kb_{customer_id}` pro Mandant | `qdrant_store.py`, `customers.collection_name` |
| **Retrieval** | Suche nur in erlaubten Collections | `retrieval.py` |
| **Admin Slug** | `global` nicht als Tenant anlegbar/umbenennbar | `customers.py`, `users_admin.py` |
| **Uploads FS** | Pfad `./data/uploads/{customer_id}/` | `upload.py` |

---

## `user_has_customer` — Sonderfälle

- **`global` als aktiver Kunde:** erlaubt, wenn User **mindestens einen** Mandanten zugewiesen hat
- **Normaler Slug:** Eintrag in `user_customers` + `customers.active == 1`
- **Ungültiger Slug:** abgelehnt (`validate_customer_slug`)

---

## Was der Client **nicht** tun darf

- `customer_id` in Chat-/Document-Body als Autorität nutzen (wird ignoriert oder überschrieben)
- Fremde `chat_id` / `document_id` erraten — Server prüft Ownership

---

## Global-KB vs Mandanten-KB

| Collection | Inhalt | Wer sieht/sucht |
|---|---|---|
| `kb_global` | Unternehmensweite KB | Bei Tenant-Chat: anteilig; bei Global-Modus: plus alle zugewiesenen |
| `kb_{tenant}` | Mandantenspezifisch | Nur dieser Mandant (+ Global-Merge in scoped search) |

---

## Tests (Pflicht-Gates)

| Test | Prüft |
|---|---|
| `test_tenant_isolation.py` | Cross-Tenant Documents/Chat |
| `test_admin_customers.py` | Slug-Regeln, Rename |
| `test_global_customer.py` | Global-Suchverhalten |
| `test_upload_api.py` / `test_documents_api.py` | Scoped API |

Details: [`10_testing_landscape.md`](./10_testing_landscape.md)

---

## Betroffene Spiegel-Dateien

`tenant.md`, `customers.md`, `auth.md`, `chats.md`, `ingestion.md`, `retrieval.md`, `qdrant_store.md`, `upload.md`, `tests/test_tenant_isolation.md`
