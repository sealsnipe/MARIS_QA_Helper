# `backend/app/templates/admin_users.html`

**Quellpfad:** `backend/app/templates/admin_users.html`

## Zweck und logischer Aufbau

Jinja2-Template für die **Administration von Anwendungsbenutzern**. Es erweitert `layout.html` und liefert nur den Seiteninhalt (`content`-Block): Formular zum Anlegen neuer Benutzer sowie eine Tabelle aller Benutzer mit Inline-Bearbeitung.

Die Seite wird ausschließlich für Administratoren unter `/admin/users` ausgeliefert (`admin_users_page` in `routes.py`). Sichtbare Texte und Formularfelder sind auf Deutsch; die eigentliche CRUD-Logik liegt vollständig in `app.js` (`initUsersPage`) und den REST-Endpunkten unter `/api/admin/users`.

Lesereihenfolge: `extends` und Block-Overrides (`title`, `page_title`) → Einleitungstext → Erstellungsformular → Benutzerliste (Tabelle + Leerzustand) → globaler Listen-Status.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html` (Basis-Layout mit Sidebar, `APP_BOOT`, `app.js`)
- **Wird genutzt von:** `backend/app/routes.py` — `admin_users_page` (`GET /admin/users`, `active_page="admin_users"`)
- **HTTP / UI / CLI:**
  - Seite: `GET /admin/users` (Admin-Pflicht, sonst Redirect)
  - API (via JS): `GET/POST /api/admin/users`, `PATCH/DELETE /api/admin/users/{user_id}`
- **Daten:** SQLite-Tabellen `User`, `UserCustomer`, `Customer` (über Admin-API)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | Browser-Titel: „Benutzer · MARIS - Q/A Helper“ |
| `page_title` | Jinja-Block | Überschrift in der Hauptspalte: „Benutzer“ |
| `content` | Jinja-Block | Gesamter Seiteninhalt (Panel, Formular, Tabelle) |

Keine Python-Symbole — reines HTML/Jinja-Markup.

## Funktionen und Klassen

Keine — die Datei definiert kein ausführbares Python- oder JavaScript.

## HTML / JS / CSS — zusätzliche Hinweise

- **extends:** `layout.html` — Sidebar, Kundenauswahl, `APP_BOOT.page = "admin_users"`, globales Laden von `/static/app.js`
- **Page-Boot:** `initUsersPage()` in `app.js`, ausgelöst wenn `APP_BOOT.page === "admin_users"`
- **Wichtige Element-IDs:**

| ID | Zweck |
|---|---|
| `user-create-form` | Formular Neuer Benutzer (Submit → `POST /api/admin/users`) |
| `user-create-email` | E-Mail (Pflicht, max. 200 Zeichen) |
| `user-create-password` | Passwort (Pflicht, min. 8 Zeichen) |
| `user-create-admin` | Checkbox Administrator |
| `user-create-customers` | Container für Kunden-Checkboxen (dynamisch befüllt) |
| `user-create-submit` | Submit-Button „Anlegen“ |
| `user-create-status` | Statusmeldung Erstellung (`aria-live="polite"`) |
| `user-count` | Anzahl Benutzer in Klammern |
| `user-table` / `user-table-body` | Benutzertabelle (Zeilen per JS gerendert) |
| `user-empty` | Leerzustand „Noch keine Benutzer.“ |
| `user-list-status` | Status für Listen-/Bearbeitungsaktionen |

- **CSS-Klassen:** `panel`, `customer-admin-panel`, `ingest-form`, `customer-create-form`, `customer-table`, `user-form-row`, `user-customers-fieldset`
- **Inline-Bearbeitung:** Wird per JS als zusätzliche Tabellenzeilen (`.user-edit-row`) eingefügt, nicht im statischen HTML
