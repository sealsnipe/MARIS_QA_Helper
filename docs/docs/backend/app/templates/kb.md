# `backend/app/templates/kb.html`

**Quellpfad:** `backend/app/templates/kb.html`

## Zweck und logischer Aufbau

Jinja2-Template für die **Wissensdatenbank-Ansicht** regulärer (nicht-admin) Benutzer unter `/kb`. Es zeigt Ingestion-Formular (Titel, optionaler Text, Datei-Dropzone) und eine Dokumentenliste für den aktiven Mandanten.

Administratoren werden serverseitig von `/kb` nach `/admin/knowledge` umgeleitet (`kb_page` in `routes.py`). Bei Auswahl des globalen Kunden (`global`) schaltet `initKbPage()` in Leseansicht (Banner `#kb-readonly-banner`, deaktiviertes Ingestion-Formular).

Lesereihenfolge: Layout-Vererbung → KB-Panel mit optionalem Readonly-Banner → Ingestion → Dokumentenliste.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html`
- **Wird genutzt von:** `backend/app/routes.py` — `kb_page` (`GET /kb`, `active_page="kb"`, nur Nicht-Admins)
- **HTTP / UI / CLI:**
  - Seite: `GET /kb` (Redirect für Admins)
  - API (via JS): `GET/POST /api/documents`, `DELETE /api/documents/{id}` (über `bindIngestForm` / `refreshKbDocuments`)
- **Daten:** SQLite `Document`; Qdrant-Collection pro `customer_id`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | Browser-Titel: „Wissensdatenbank · MARIS - Q/A Helper“ |
| `page_title` | Jinja-Block | Seitenüberschrift: „Wissensdatenbanken“ |
| `content` | Jinja-Block | Vollseiten-KB-Panel (`full-page`) |

## Funktionen und Klassen

Keine — reines Markup-Template.

## HTML / JS / CSS — zusätzliche Hinweise

- **extends:** `layout.html` — `APP_BOOT.page = "kb"`
- **Page-Boot:** `initKbPage()` bei `APP_BOOT.page === "kb"`
- **Wichtige Element-IDs:**

| ID | Zweck |
|---|---|
| `kb-customer-name` | Anzeigename des aktiven Kunden (per JS gesetzt) |
| `kb-readonly-banner` | Hinweis Leseansicht Global (initial `hidden`) |
| `ingest-form` | Upload-/Text-Ingestion |
| `ingest-title` | Optionaler Dokumenttitel |
| `ingest-text` | Optionaler Einleitungstext / Schlagworte |
| `dropzone` / `file-input` / `file-label` | Datei-Upload (.txt, .md, .pdf, .docx, max. 30 MB) |
| `ingest-submit` | Button „Einpflegen“ |
| `ingest-status` | Statusmeldung Ingestion |
| `doc-count` | Dokumentanzahl |
| `doc-list` | Liste indizierter Dokumente |
| `doc-empty` | Leerzustand |

- **API-Pfad (JS):** `POST /api/documents` (Multipart), Liste via `GET /api/documents`
- **CSS-Klassen:** `kb-panel`, `full-page`, `ingest-form`, `dropzone`, `doc-list-wrap`, `banner info`
