# 05 — API-Spezifikation

**Stand:** 2026-06-03 · **Status:** verbindlich (Admin-API, Vision-OCR, Inspect)

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
| POST | `/api/documents/inspect` | Multipart | ✅ | ✅ | **Datei auf Bilder prüfen** (Vorschau) |
| POST | `/api/documents` | Multipart | ✅ | ✅ | **Datei-Upload** (+ optional Vision-OCR) |
| DELETE | `/api/documents/{id}` | JSON | ✅ | ✅ | Dokument löschen |
| POST | `/api/chat` | JSON | ✅ | ✅ | Frage stellen (Agent); optional `chat_id` |
| POST | `/api/v1/ask` | JSON | Bearer | Body | **Integration:** Frage stellen (externe Agenten) |
| POST | `/api/v1/knowledge-content` | JSON | Bearer | — | **Integration:** Content-Vorschläge für Knowledge Center |
| GET | `/tools/knowledge-center/submit` | HTML | ✅ | — | Content vorschlagen (User) |
| GET | `/tools/knowledge-center` | HTML | ✅ Admin | — | Content Dashboard (Review) |
| GET | `/tools/knowledge-center/sources` | HTML | ✅ Admin | — | Knowledge Center Sources |
| GET | `/api/tools/knowledge-center/submit-context` | JSON | ✅ | — | Mandanten + KI-Presets für Submit |
| POST | `/api/tools/knowledge-center/submit` | JSON | ✅ | Body | Vorschlag einreichen (optional KI) |
| GET | `/api/tools/knowledge-center/my-contents` | JSON | ✅ | — | Eigene Vorschläge (User) |
| GET | `/api/tools/knowledge-center/contents` | JSON | ✅ Admin | — | Review-Queue |
| GET | `/api/tools/knowledge-center/contents/{id}` | JSON | ✅ | — | Content-Detail |
| POST | `/api/tools/knowledge-center/contents/{id}/adopt` | JSON | ✅ Admin | Body | In KB übernehmen |
| POST | `/api/tools/knowledge-center/contents/{id}/reject` | JSON | ✅ Admin | — | Vorschlag ablehnen |
| GET/POST/PATCH/DELETE | `/api/admin/knowledge-sources[/{id}]` | JSON | ✅ Admin | — | Knowledge Center Sources CRUD |
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
| GET/POST/PATCH/DELETE | `/api/admin/roles[/{id}]` | JSON | ✅ Admin | Rollen-CRUD (Presets) |
| GET/PATCH | `/api/admin/keys[/*]` | JSON | ✅ Admin | Chat/Embed/Similarity/Integration Keys + OAuth-Device-Flow |

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

### 3.6 `POST /api/documents/inspect`
- Multipart: Feld `file` (eine Datei).
- Unterstützt `.pdf`, `.docx`, standalone Bilder (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`).
- Erfolg `200`:
  ```json
  {
    "has_images": true,
    "image_count": 3,
    "file_type": "docx",
    "text_extractable": true,
    "image_only": false,
    "pages_with_images": [],
    "filename": "guide.docx",
    "images": [
      {
        "id": "img_001",
        "page": null,
        "label": "img_001",
        "preview_data_url": "data:image/png;base64,..."
      }
    ]
  }
  ```
- Fehler: `400 unsupported_file_type`, `413 file_too_large`, `422 inspection_failed`.
- Admin-Spiegel: `POST /api/admin/documents/inspect`, `POST /api/admin/customers/{id}/documents/inspect`.

### 3.7 `POST /api/documents` (Datei-Upload)
- Multipart: Feld `file` (eine Datei), optional `title`, optional Prefix-Feld `text`, optional `process_images=true`, optional `transcribe_image_ids` (JSON-Array, z. B. `["img_001","img_003"]`).
- Erlaubte Typen: `.txt`, `.md`, `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`.
- Schritte: Typ/Größe prüfen → speichern unter `./data/uploads/{customer_id}/{document_id}/` → ggf. **Inspect** (Bilder) → Loader extrahiert Text → optional **Vision-OCR** (nur ausgewählte Bild-IDs) → alle Bilder werden unter `…/images/` gespeichert → `ingest_text`.
- **DOCX:** OCR-Blöcke `[BILD id="…"]…[/BILD]` **inline** im Fließtext; nicht transkribierte Bilder als Platzhalter `status="nicht_verarbeitet"`.
- **PDF / standalone Bild:** OCR-Blöcke am Ende (PDF mit `seite="N"`); standalone Bild nur mit Vision-OCR oder Prefix-Text.
- Erfolg `200`:
  ```json
  { "document": { "id":"uuid","customer_id":"acme","title":"VPN Runbook",
      "source_type":"pdf","original_filename":"vpn.pdf","status":"indexed","chunk_count":3,
      "extraction_meta": { "image_count": 2, "images_processed": 1, "vision_used": true, "coverage": "partial", "images": [...] } } }
  ```
- Fehler:
  - `400 {"error":"unsupported_file_type"}` — Extension nicht erlaubt.
  - `413 {"error":"file_too_large"}` — über `MAX_UPLOAD_MB`.
  - `422 {"error":"extraction_failed"}` — leeres/kaputtes Dokument ohne Bilder.
  - `422 {"error":"images_only_requires_vision"}` — nur Bilder, kein Text, Vision nicht gewählt.
  - `422 {"error":"vision_failed"}` — Vision-OCR für ausgewählte Bilder fehlgeschlagen.
  - `422 {"error":"inspection_failed"}` — Inspect fehlgeschlagen.
  - `502 embedding_failed` / `vector_store_failed`.

### 3.8 `GET /api/documents/{id}/images/{image_id}` (Admin + Tenant)
- Liefert extrahiertes Bild aus `./data/uploads/…/images/` (Authentifizierung + Mandanten-Check).
- Nutzung: Thumbnails im Admin-Editor, Lightbox.

### 3.9 `DELETE /api/documents/{id}`
- Prüft `document.customer_id == aktiver Kunde` (sonst `403`/`404`), löscht Qdrant-Points + setzt
  `deleted_at`. Erfolg `200 {"deleted":true,"id":"uuid"}`. Unbekannt → `404`.

### 3.10 `POST /api/chat`
Request `{ "message":"…", "top_k":6, "chat_id":"uuid-optional" }`.
Erfolg `200`:
```json
{ "chat_id":"uuid","chat_title":"…","customer_id":"acme","answer":"… [1] …",
  "sources":[ {"n":1,"document_id":"uuid","title":"VPN Runbook","chunk_index":4,"score":0.82} ],
  "no_context": false }
```
- `no_context:true` + leere `sources` wenn keine Treffer über `MIN_SCORE_DEFAULT`.
- `sources` nur aus Retrieval (FR-15). Fehler: `400 empty_message`, `502 llm_failed`.

### 3.11 `GET /api/health`
`{ "ok": true }` — ohne Auth.

### 3.12 `POST /api/v1/ask` (Integration)

Maschinen-API für externe Agenten (Cursor, n8n, eigene Scripts). Details: [`system/12_integration_api.md`](../system/12_integration_api.md).

**Auth:** `Authorization: Bearer <INTEGRATION_API_TOKEN>` (`.env`; leer = Endpoint `503 integration_disabled`).

Request:
```json
{
  "question": "Wie richte ich VPN ein?",
  "customer_id": "bg-frankfurt",
  "chat_id": "uuid-optional",
  "top_k": 4
}
```

Erfolg `200`:
```json
{
  "answer": "… [1] …",
  "sources": [
    { "n": 1, "document_id": "uuid", "title": "VPN Runbook", "chunk_index": 4, "score": 0.82 }
  ],
  "no_context": false,
  "chat_id": "uuid",
  "customer_id": "bg-frankfurt"
}
```

- `customer_id` im Body (nur bei gültigem Bearer-Token); Kunde muss existieren und aktiv sein.
- `chat_id` optional — ohne ID neuer Chat; gleiche ID für Follow-ups (Persistenz unter Integration-Service-User).
- Fehler: `401 invalid_token`, `400 empty_question`, `403 forbidden_customer`, `404 not_found`, `503 integration_disabled` / `integration_user_missing`, `502 llm_failed`.

## 4. Statuscodes
| Code | Bedeutung |
|---|---|
| 200 | OK |
| 302 | Redirect (Login/Logout) |
| 400 | Validierungsfehler / unsupported_file_type / empty_* |
| 401 | nicht authentifiziert / invalid_token (Integration) |
| 403 | forbidden_customer (kein Zugriff auf Kunden) |
| 404 | nicht gefunden |
| 413 | file_too_large |
| 422 | extraction_failed / images_only_requires_vision / vision_failed / inspection_failed |
| 502 | Upstream-Fehler (OpenAI/Qdrant) |
| 503 | integration_disabled / integration_user_missing |

## 5. Admin-API (Kurz)

Details: [`system/06_admin_flows.md`](../system/06_admin_flows.md), Spiegel `docs/docs/backend/app/routes.md`.

- **Kunden:** `POST {customer_id, name}`; `PATCH {name}` oder `{id, name}` für Slug-Rename; `DELETE` deaktiviert
- **User:** `POST {email, password, customer_ids, is_admin}`; `PATCH` partial; `DELETE` deaktiviert
- **Prompt:** `PUT {customer_id?, content}` — `customer_id` null = global
- **KB-Dokument bearbeiten:** `GET /api/admin/documents/{id}` bzw. `GET …/customers/{cid}/documents/{id}` → `{ document, text, editable, from_file }`; `PUT` mit `{ title, text }` → Re-Index (gleiche `document_id`, `source_text` in SQLite). 404 bei falschem Mandanten/Dokument.
- Fehlercodes: `customer_exists`, `invalid_customer_id`, `user_exists`, `cannot_deactivate_self`, …

## 6. Nicht im MVP / Roadmap
`POST /api/jira/import` (Roadmap). Reiner `/api/search` für Endnutzer (Agent kapselt Suche).
