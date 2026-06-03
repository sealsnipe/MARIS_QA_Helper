# 05 — API-Spezifikation

**Stand:** 2026-06-03 · **Status:** verbindlich (Admin-API ergänzt)

> Querschnitt: [`system/02_request_and_session_flow.md`](../system/02_request_and_session_flow.md), [`system/06_admin_flows.md`](../system/06_admin_flows.md)

---

## 1. Konventionen

- **Base:** `http://localhost:8088`
- **Content-Type:** JSON-API: `application/json`; Login: `x-www-form-urlencoded`; Upload:
  `multipart/form-data`.
- **Auth:** Session-Cookie (siehe `07`). Geschützte Routen ohne gültige Session:
  - HTML → `302` Redirect `/login`
  - JSON → `401 {"error":"not_authenticated"}`
- **Mandant:** Der **aktive Kunde** kommt **aus der Session**, nie aus Request-Parametern.
  Operation auf einem Kunden ohne Berechtigung → `403 {"error":"forbidden_customer"}`.
- **Fehlerformat (JSON):** `{ "error": "<code>", "detail": "<optional>" }` — keine Stacktraces/Secrets.
- **Zeit/IDs:** ISO-8601 UTC; UUIDv4 (außer `customer_id` = Slug).

## 2. Routenübersicht

| Methode | Pfad | Typ | Auth | Mandant-scoped | Zweck |
|---|---|---|---|---|---|
| GET | `/` | HTML | ✅ | — | Redirect `/chat` |
| GET | `/login` | HTML | — | — | Login-Formular |
| POST | `/login` | Form | — | — | Login durchführen |
| POST | `/logout` | Form/JSON | ✅ | — | Logout |
| GET | `/api/customers` | JSON | ✅ | — | Für Nutzer erlaubte Kunden |
| POST | `/api/session/customer` | JSON | ✅ | — | Aktiven Kunden setzen/wechseln |
| GET | `/api/documents` | JSON | ✅ | ✅ | Dokumentliste (aktiver Kunde) |
| POST | `/api/documents/text` | JSON | ✅ | ✅ | Text einpflegen |
| POST | `/api/documents` | Multipart | ✅ | ✅ | **Datei-Upload** |
| DELETE | `/api/documents/{id}` | JSON | ✅ | ✅ | Dokument löschen |
| POST | `/api/chat` | JSON | ✅ | ✅ | Frage stellen (Agent); optional `chat_id` |
| GET | `/chat` | HTML | ✅ | ✅ | Chat (Sidebar-Historie) |
| GET | `/kb` | HTML | ✅ | ✅ | Wissensbasis (Nutzer) |
| GET | `/admin/customers` | HTML | ✅ Admin | — | Kunden-Admin |
| GET | `/admin/knowledge` | HTML | ✅ Admin | — | KB-Admin (global/Scope) |
| GET | `/admin/prompts` | HTML | ✅ Admin | — | Systemprompts |
| GET | `/admin/users` | HTML | ✅ Admin | — | Benutzer-Admin |
| GET | `/api/chats` | JSON | ✅ | ✅ | Chat-Sessions Liste |
| POST | `/api/chats` | JSON | ✅ | ✅ | Neuer Chat |
| GET | `/api/chats/{id}` | JSON | ✅ | ✅ | Chat inkl. Messages |
| DELETE | `/api/chats/{id}` | JSON | ✅ | ✅ | Chat löschen |
| GET | `/api/admin/customers` | JSON | ✅ Admin | — | Alle Mandanten |
| POST/PATCH/DELETE | `/api/admin/customers[/{id}]` | JSON | ✅ Admin | — | Kunden CRUD, Slug-Rename |
| GET/PUT | `/api/admin/system-prompt` | JSON | ✅ Admin | — | Prompt global/pro Scope |
| GET/POST/DELETE | `/api/admin/documents[/{id}]` | JSON | ✅ Admin | global KB; **GET/PUT `{id}`** = Inhalt lesen/bearbeiten |
| GET/POST/DELETE | `/api/admin/customers/{id}/documents[/{doc}]` | JSON | ✅ Admin | pro Mandant; **GET/PUT `{doc}`** = Bearbeiten |
| GET/POST/PATCH/DELETE | `/api/admin/users[/{id}]` | JSON | ✅ Admin | Benutzer-CRUD |

> Alle mandant-gescopten Routen ziehen `customer_id` über `get_current_customer` aus der Session
> und prüfen `user ∈ customer` (sonst 403).

## 3. Endpunkte im Detail

### 3.1 `GET/POST /login`, `POST /logout`
- `GET /login`: rendert Formular; bereits angemeldet → Redirect `/`.
- `POST /login` (`email`, `password`): Erfolg → Session (`user_id`) + aktiven Kunden setzen, falls
  Nutzer **genau einen** Kunden hat; `302` → `/`. Fehlschlag → Formular mit generischer Meldung.
- `POST /logout`: Session leeren → `302` `/login`.

### 3.2 `GET /api/customers`
```json
{ "customers": [ {"id":"acme","name":"Acme GmbH"}, {"id":"globex","name":"Globex AG"} ],
  "active": "acme" }
```
- Nur Kunden, für die der Nutzer berechtigt ist. `active` = aktueller Session-Kunde (oder `null`).

### 3.3 `POST /api/session/customer`
```json
{ "customer_id": "globex" }
```
- Prüft `user ∈ customer`. Erfolg → `session["customer_id"]=globex`, `200 {"active":"globex"}`.
- Nicht berechtigt → `403 {"error":"forbidden_customer"}`; unbekannt → `404`.

### 3.4 `GET /api/documents`
```json
{ "customer_id":"acme",
  "documents":[ {"id":"uuid","title":"VPN Runbook","source_type":"file",
    "original_filename":"vpn.pdf","chunk_count":3,"status":"indexed",
    "created_at":"2026-06-02T10:00:00Z"} ] }
```
- Nur aktive Dokumente des aktiven Kunden, neueste zuerst.

### 3.5 `POST /api/documents/text`
Request `{ "title":"VPN Runbook", "text":"..." }`. Validierung: `title` 1..200; `text` nach
Normalisierung ≥ 20 Zeichen sonst `400 empty_text`.
Erfolg `200 {"document":{...,"source_type":"manual","status":"indexed","chunk_count":3}}`.
Fehler: `400 empty_text`, `502 embedding_failed`, `502 vector_store_failed` (jeweils kein
`indexed`-Doc).

### 3.6 `POST /api/documents` (Datei-Upload)
- Multipart: Feld `file` (eine Datei), optional `title` (Default: Dateiname).
- Schritte: Typ prüfen (`.txt/.md/.pdf/.docx`) → Größe ≤ `MAX_UPLOAD_MB` → Filename sanitizen →
  speichern unter `./data/uploads/{customer_id}/{document_id}/` → Loader extrahiert Text →
  `ingest_text(customer_id, ...)`.
- Erfolg `200`:
  ```json
  { "document": { "id":"uuid","customer_id":"acme","title":"VPN Runbook",
      "source_type":"file","original_filename":"vpn.pdf","status":"indexed","chunk_count":3 } }
  ```
- Fehler:
  - `400 {"error":"unsupported_file_type"}` — Extension nicht erlaubt.
  - `413 {"error":"file_too_large"}` — über `MAX_UPLOAD_MB`.
  - `422 {"error":"extraction_failed"}` — leeres/kaputtes Dokument → `status=failed` gespeichert,
    **nichts** in Qdrant.
  - `502 embedding_failed` / `vector_store_failed`.

### 3.7 `DELETE /api/documents/{id}`
- Prüft `document.customer_id == aktiver Kunde` (sonst `403`/`404`), löscht Qdrant-Points + setzt
  `deleted_at`. Erfolg `200 {"deleted":true,"id":"uuid"}`. Unbekannt → `404`.

### 3.8 `POST /api/chat`
Request `{ "message":"…", "top_k":6, "chat_id":"uuid-optional" }`.
Erfolg `200`:
```json
{ "chat_id":"uuid","chat_title":"…","customer_id":"acme","answer":"… [1] …",
  "sources":[ {"n":1,"document_id":"uuid","title":"VPN Runbook","chunk_index":4,"score":0.82} ],
  "no_context": false }
```
- `no_context:true` + leere `sources` wenn keine Treffer über `MIN_SCORE_DEFAULT`.
- `sources` nur aus Retrieval (FR-15). Fehler: `400 empty_message`, `502 llm_failed`.

### 3.9 `GET /api/health`
`{ "ok": true }` — ohne Auth.

## 4. Statuscodes
| Code | Bedeutung |
|---|---|
| 200 | OK |
| 302 | Redirect (Login/Logout) |
| 400 | Validierungsfehler / unsupported_file_type / empty_* |
| 401 | nicht authentifiziert |
| 403 | forbidden_customer (kein Zugriff auf Kunden) |
| 404 | nicht gefunden |
| 413 | file_too_large |
| 422 | extraction_failed |
| 502 | Upstream-Fehler (OpenAI/Qdrant) |

## 5. Admin-API (Kurz)

Details: [`system/06_admin_flows.md`](../system/06_admin_flows.md), Spiegel `docs/docs/backend/app/routes.md`.

- **Kunden:** `POST {customer_id, name}`; `PATCH {name}` oder `{id, name}` für Slug-Rename; `DELETE` deaktiviert
- **User:** `POST {email, password, customer_ids, is_admin}`; `PATCH` partial; `DELETE` deaktiviert
- **Prompt:** `PUT {customer_id?, content}` — `customer_id` null = global
- **KB-Dokument bearbeiten:** `GET /api/admin/documents/{id}` bzw. `GET …/customers/{cid}/documents/{id}` → `{ document, text, editable, from_file }`; `PUT` mit `{ title, text }` → Re-Index (gleiche `document_id`, `source_text` in SQLite). 404 bei falschem Mandanten/Dokument.
- Fehlercodes: `customer_exists`, `invalid_customer_id`, `user_exists`, `cannot_deactivate_self`, …

## 6. Nicht im MVP / Roadmap
`POST /api/jira/import` (Roadmap). Reiner `/api/search` für Endnutzer (Agent kapselt Suche).
