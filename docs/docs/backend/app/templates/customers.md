# `backend/app/templates/customers.html`

**Quellpfad:** `backend/app/templates/customers.html`

## Zweck und logischer Aufbau

Jinja2-Template für die **Administration von Mandanten (Kunden)**. Administratoren können hier Slug und Anzeigenamen anlegen, umbenennen oder deaktivieren. Ein ausführlicher Einleitungstext erklärt die Folgen einer Slug-Änderung: Migration von Qdrant-Collections, Uploads und Chat-Verläufen.

Die Seite wird unter `/admin/customers` ausgeliefert. Formular und Tabelle sind statisches HTML; alle CRUD- und Migrationsoperationen laufen über `initCustomersPage()` in `app.js` und `/api/admin/customers`.

Lesereihenfolge: Layout-Vererbung → Einleitung → Erstellungsformular → Kundenliste → Listen-Status.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html`
- **Wird genutzt von:** `backend/app/routes.py` — `admin_customers_page` (`GET /admin/customers`, `active_page="customers"`)
- **HTTP / UI / CLI:**
  - Seite: `GET /admin/customers` (Admin-Pflicht)
  - API (via JS): `GET/POST /api/admin/customers`, `PATCH/DELETE /api/admin/customers/{id}`
- **Daten:** SQLite `Customer`; bei Umbenennung Qdrant-Collections, `Document`, `Chunk`, Upload-Pfade, Chat-Referenzen (Backend-Logik in `customers.py`)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | Browser-Titel: „Kunden · MARIS - Q/A Helper“ |
| `page_title` | Jinja-Block | Seitenüberschrift: „Kundenverwaltung“ |
| `content` | Jinja-Block | Admin-Panel mit Formular und Tabelle |

## Funktionen und Klassen

Keine — reines Markup-Template.

## HTML / JS / CSS — zusätzliche Hinweise

- **extends:** `layout.html` — `APP_BOOT.page = "customers"`
- **Page-Boot:** `initCustomersPage()` bei `APP_BOOT.page === "customers"`
- **Wichtige Element-IDs:**

| ID | Zweck |
|---|---|
| `customer-create-form` | Formular „Neuer Kunde“ |
| `customer-create-id` | Kunden-ID / Slug (max. 64, Pflicht) |
| `customer-create-name` | Anzeigename (max. 200, Pflicht) |
| `customer-create-submit` | Button „Anlegen“ |
| `customer-create-status` | Statusmeldung Erstellung |
| `customer-count` | Anzahl Kunden in Klammern |
| `customer-table` / `customer-table-body` | Kundenliste (Zeilen per JS) |
| `customer-empty` | Leerzustand |
| `customer-list-status` | Status für Laden/Speichern/Löschen/Migration |

- **Inline-Bearbeitung:** Bearbeiten/Speichern/Abbrechen per JS-Klassen (`.customer-edit-btn`, `.customer-save-btn`, …) in Tabellenzeilen
- **Migration-Feedback:** Bei Slug-Änderung zeigt JS Fortschritt („… migriere KB (Qdrant) …“) und Erfolgsmeldung — siehe Einleitungstext im Template
- **CSS-Klassen:** `customer-admin-panel`, `customer-form-row`, `customer-table`, `ingest-form`
