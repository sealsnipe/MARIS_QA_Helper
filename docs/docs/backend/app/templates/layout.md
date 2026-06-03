# `backend/app/templates/layout.html`

**Quellpfad:** `backend/app/templates/layout.html`

## Zweck und logischer Aufbau

**Haupt-Layout** der Anwendung nach dem Sidebar-Redesign. Es definiert das vollständige HTML-Dokument mit linker Navigation (Marke, Kundenauswahl, Chat-Historie, Admin-Untermenü), rechter Hauptspalte (Seitentitel, Inhalt) und globalem JavaScript-Boot (`APP_BOOT`).

Fast alle authentifizierten App-Seiten erben dieses Template: Chat, KB, Admin-Bereiche (Kunden, Wissensdatenbanken, Prompts, Benutzer). Login und Legacy-`index.html` nutzen stattdessen `base.html`.

Lesereihenfolge: HTML-Head → Sidebar (`aside`) mit Nav → Hauptbereich (`main-area`) → inline `APP_BOOT` → optional `vendor_scripts` → `app.js` → optional `scripts`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `/static/brand-icon.svg`, `/static/brand-banner.svg`, `/static/app.css`, `/static/app.js`
- **Wird genutzt von:**
  - `chat.html`, `kb.html`, `customers.html`, `admin_users.html`
  - `admin_knowledge.html`, `admin_prompts.html` (nicht in diesem Spiegel-Batch)
- **HTTP / UI / CLI:** Indirekt über Kind-Routen; Sidebar nutzt `POST /logout`, Kundenwechsel via `POST /api/session/customer`
- **Daten:** Jinja-Kontext aus `_page_context` in `routes.py` (User, Kunden, Admin-Flag, aktive Seite)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | Browser-Titel; Default „MARIS - Q/A Helper“ |
| `page_title` | Jinja-Block | `<h1>` in der Hauptspalte |
| `content` | Jinja-Block | Seiteninhalt in `#page-content` |
| `vendor_scripts` | Jinja-Block | Zusätzliche Skripte vor `app.js` (z. B. Markdown in `chat.html`) |
| `scripts` | Jinja-Block | Seitenspezifische Skripte nach `app.js` |

### Jinja-Kontext (von `_page_context`)

| Name | Art | Beschreibung |
|---|---|---|
| `user` | `User` | Angemeldeter Benutzer |
| `customers` | Liste | Navigations-Kunden des Users |
| `admin_customers` | Liste | Alle Mandanten (Admin-Kontext) |
| `active_customer` | `Customer` \| None | Session-Kunde |
| `is_admin` | `bool` | Admin-Navigation sichtbar |
| `active_page` | `str` | Seiten-ID für CSS (`page-{{ active_page }}`) und JS (`APP_BOOT.page`) |
| `global_customer_id` | `str` | ID des globalen KB-Mandanten |
| `customer_labels` | `dict` | `{ customer_id: name }` für UI-Labels |

### Lokale Jinja-Variablen

| Name | Art | Beschreibung |
|---|---|---|
| `admin_nav_pages` | Liste | `['customers', 'admin_knowledge', 'admin_prompts', 'admin_users']` — steuert aufgeklapptes Admin-Menü |

## Funktionen und Klassen

Keine — Layout-Template ohne Python-Logik.

## HTML / JS / CSS — zusätzliche Hinweise

- **Body-Klasse:** `page-{{ active_page }}` — seitenbezogene CSS-Hooks
- **Sidebar-Struktur:**
  - `#customer-select` — Mandantenauswahl (leer wenn keine Kunden)
  - `#chat-nav-section` — „+ Neuer Chat“, `#chat-history-list`
  - `#admin-nav-group` — nur wenn `is_admin`; Links zu `/admin/customers`, `/admin/knowledge`, `/admin/prompts`, `/admin/users`
  - Footer: `user.email`, `POST /logout`
- **`APP_BOOT` (inline):**

| Feld | Bedeutung |
|---|---|
| `page` | Aktive Seite (`active_page`) |
| `activeCustomerId` / `activeCustomerName` | Session-Mandant |
| `globalCustomerId` | Globaler KB-Slug |
| `customerLabels` | Anzeigenamen-Map |
| `isAdmin` | Admin-Rechte |
| `adminCustomers` / `adminCustomerNames` | IDs und Namen aller Mandanten für Admin-UI |

- **Globale JS-Init (app.js):** Kundenauswahl, `#no-customer-banner`, Chat-Sidebar, `initAdminNav()`, dann seiten-spezifische `init*Page()` anhand `boot.page`
- **Wichtige Element-IDs:** `no-customer-banner`, `page-content`, `new-chat-btn`, `chat-history-list`, `admin-nav-toggle`, `admin-nav-submenu`, `customer-select`
