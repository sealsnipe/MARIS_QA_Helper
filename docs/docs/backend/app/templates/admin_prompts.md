# `backend/app/templates/admin_prompts.html`

**Quellpfad:** `backend/app/templates/admin_prompts.html`

## Zweck und logischer Aufbau

Admin-Seite **Systemprompts**: Auswahl des Scopes (global oder Kunde), großes Textarea zum Bearbeiten und Speichern des System-Prompts. Erweitert `layout.html`; Interaktion über `app.js` → `initAdminPromptsPage`.

Globaler Prompt gilt für alle Mandanten; kundenspezifischer Text wird ergänzend an den globalen Prompt angehängt (siehe `system_prompts.get_effective_system_prompt`).

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `layout.html` — Shell, Navigation, `APP_BOOT`
  - Jinja: `admin_customers` für Scope-Dropdown
- **Wird genutzt von:**
  - `routes.admin_prompts_page` — `GET /admin/prompts`
  - `app.js` — `initAdminPromptsPage`
- **HTTP / UI:**
  - Seite: `/admin/prompts`, `active_page="admin_prompts"`
  - APIs: `GET /api/admin/system-prompt`, `PUT /api/admin/system-prompt`
- **Daten:** SQLite `SystemPrompt` (global / pro Mandant)

## Konstanten, Typen und Modulebene

| Block / Element | Beschreibung |
|---|---|
| `{% block title %}` | „Systemprompts · MARIS - Q/A Helper“ |
| `{% block page_title %}` | „Systemprompts“ |
| `{% block content %}` | Toolbar + Prompt-Formular |

## HTML / JS — zusätzliche Hinweise

### Wichtige Element-IDs

| ID | Rolle |
|---|---|
| `prompt-scope` | Select: `global` oder Kunden-ID |
| `prompt-form` | Speicher-Formular |
| `prompt-content` | Textarea (16 Zeilen) für Prompt-Text |
| `prompt-submit` | Button „Speichern“ |
| `prompt-status` | Statuszeile (`aria-live="polite"`) |

### JS-Init

- `APP_BOOT.page === "admin_prompts"` → `initAdminPromptsPage()`
- Beim Laden/Scope-Wechsel: `GET /api/admin/system-prompt?customer_id=…` (leer bei global)
- Submit: `PUT /api/admin/system-prompt` mit `{ customer_id: null | id, content }`

## Siehe auch

- [`../system_prompts.md`](../system_prompts.md) — Prompt-Zusammenbau
- [`../routes.md`](../routes.md) — `admin_prompts_page`, Prompt-APIs
- [`../static/app.md`](../static/app.md) — `initAdminPromptsPage`
