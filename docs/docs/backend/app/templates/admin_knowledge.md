# `backend/app/templates/admin_knowledge.html`

**Quellpfad:** `backend/app/templates/admin_knowledge.html`

## Zweck und logischer Aufbau

Admin-Seite **Wissensdatenbanken**: Mandantenauswahl (global oder Kunde), Formular zum Einpflegen von Dokumenten, **inline Bearbeiten** bestehender Dokumente (Stift-Icon) und Liste vorhandener Dokumente. Erweitert `layout.html`; Client-Logik in `app.js` → `initAdminKnowledgePage`, `openAdminDocumentEditor`.

Struktur: Toolbar mit Scope-Select → Panel `#admin-knowledge-panel` mit Ingest-Formular (Titel, Text, Dropzone) → Dokumentenliste. Jinja liefert `admin_customers` aus `_page_context` für die Select-Optionen.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `layout.html` — Basis-Layout, Sidebar, `APP_BOOT`
  - Jinja-Kontext: `admin_customers` (aus `routes._page_context`)
- **Wird genutzt von:**
  - `routes.admin_knowledge_page` — `GET /admin/knowledge`
  - `app.js` — `initAdminKnowledgePage`, `bindIngestForm`, `refreshAdminDocuments`
- **HTTP / UI:**
  - Seite: `/admin/knowledge`, `active_page="admin_knowledge"`
  - APIs: `/api/admin/documents`, `/api/admin/customers/{id}/documents`; **GET/PUT** `…/{document_id}` für Bearbeiten
- **Daten:** Globale KB (`GLOBAL_CUSTOMER_ID`) oder mandantenspezifische Dokumente

## Konstanten, Typen und Modulebene

Keine Python-Symbole — reines Jinja2-Template.

| Block / Element | Beschreibung |
|---|---|
| `{% block title %}` | Browser-Titel „Wissensdatenbanken · MARIS - Q/A Helper“ |
| `{% block page_title %}` | Header „Wissensdatenbanken“ |
| `{% block content %}` | Hauptinhalt Admin-KB |

## HTML / JS — zusätzliche Hinweise

### Wichtige Element-IDs

| ID | Rolle |
|---|---|
| `knowledge-scope` | Select: `global` oder Kunden-ID |
| `knowledge-scope-label` | Anzeige aktueller Scope in Klammern |
| `knowledge-scope-hint` | Erklärtext global vs. Kunden-KB |
| `admin-ingest-form` | POST-Ingest (multipart) |
| `admin-ingest-title`, `admin-ingest-text` | Optionale Metadaten |
| `admin-dropzone`, `admin-file-input`, `admin-file-label` | Datei-Upload (.txt, .md, .pdf, .docx) |
| `admin-ingest-submit`, `admin-ingest-status` | Absenden und Status |
| `admin-doc-list`, `admin-doc-count`, `admin-doc-empty` | Dokumentenliste |

### JS-Init

- `APP_BOOT.page === "admin_knowledge"` → `initAdminKnowledgePage()`
- Scope-Wechsel lädt passende Admin-Dokument-API; Ingest-Zielpfad dynamisch global vs. `/api/admin/customers/{scope}/documents`
- Dokumentzeile: Stift öffnet inline Panel (`openAdminDocumentEditor`); Speichern → PUT + Listen-Refresh

## Siehe auch

- [`../routes.md`](../routes.md) — `admin_knowledge_page`, Admin-Dokument-APIs
- [`../static/app.md`](../static/app.md) — `initAdminKnowledgePage`
