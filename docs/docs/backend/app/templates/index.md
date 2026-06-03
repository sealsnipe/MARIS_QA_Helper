# `backend/app/templates/index.html`

**Quellpfad:** `backend/app/templates/index.html`

## Zweck und logischer Aufbau

**Legacy-Monolith-UI:** Eine einzige Seite mit Header (Kundenauswahl, Benutzer, Logout), Wissensdatenbank-Ingestion und Chat nebeneinander im `#workspace`. Im Gegensatz zum aktuellen Sidebar-Layout (`layout.html` + separate `/chat`- und `/kb`-Seiten) bündelt dieses Template beide Funktionen in einem Viewport.

Das Template erweitert `base.html` (nicht `layout.html`) und setzt `window.APP_BOOT` inline **ohne** `page`-Feld — `app.js` defaultet daher auf `page = "chat"`. Es wird derzeit **von keiner Route** in `routes.py` referenziert; `GET /` leitet auf `/chat` um. Die Datei bleibt als historische/alternative UI-Variante im Repo.

Lesereihenfolge: Header mit Kundensteuerung → Warn-Banner ohne Kunde → Workspace (KB-Panel links, Chat-Panel rechts) → inline `APP_BOOT` → `app.js`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `base.html`; `/static/app.js`
- **Wird genutzt von:** Derzeit keine aktive Route (früher vermutlich Haupt-UI vor Sidebar-Refactoring)
- **HTTP / UI / CLI:** Indirekt relevante Endpoints wie `/logout`, `/api/documents`, `/api/chat` (wenn Template wieder angebunden würde)
- **Daten:** Jinja-Kontext erwartet `customers`, `active_customer`, `user` (nicht über `_page_context` der aktuellen Routen)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | Browser-Titel: „SUP_QA_Helper“ |
| `content` | Jinja-Block | Vollständige App-Oberfläche inkl. Header, KB, Chat, Boot-Skript |

### Jinja-Kontext (erwartete Variablen)

| Name | Art | Beschreibung |
|---|---|---|
| `customers` | Liste | Dem Benutzer zugeordnete `Customer`-Objekte |
| `active_customer` | Objekt \| None | Aktuell gewählter Kunde aus Session |
| `user` | `User` | Angemeldeter Benutzer (`user.email` im Header) |

## Funktionen und Klassen

Keine — reines Markup mit eingebettetem Boot-Skript.

## HTML / JS / CSS — zusätzliche Hinweise

- **extends:** `base.html` — kein Sidebar, kein globales `APP_BOOT` aus Layout
- **Inline `APP_BOOT`:**

| Feld | Quelle | Bedeutung |
|---|---|---|
| `activeCustomerId` | `active_customer.id` oder `""` | Session-Kunde |
| `activeCustomerName` | `active_customer.name` oder `""` | Anzeigename |
| `customers` | IDs aller zugewiesenen Kunden | JSON-Array |
| `hasMultipleCustomers` | `customers\|length > 1` | Steuert Select vs. festes Label |

- **Kein `page`-Feld:** `app.js` nutzt Default `"chat"` — KB-Teil (`initKbPage`) wird auf dieser Seite **nicht** automatisch initialisiert, da nur `initChatPage` für `"chat"` greift; Ingestion-Elemente sind vorhanden, aber Page-Init ist unvollständig gegenüber dem Split-Layout
- **Wichtige Element-IDs:** `customer-select`, `no-customer-banner`, `workspace`, `ingest-form`, `dropzone`, `file-input`, `doc-list`, `chat-log`, `chat-form`, `chat-input`, `kb-customer-name`, `chat-customer-name`
- **Kundenauswahl-Logik:** 0 Kunden → Warnung; 1 Kunde → Hidden-Input; mehrere → `<select>`
