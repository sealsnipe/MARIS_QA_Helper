# `backend/app/templates/chat.html`

**Quellpfad:** `backend/app/templates/chat.html`

## Zweck und logischer Aufbau

Jinja2-Template für die **Chat-Oberfläche** im Sidebar-Layout. Nach Login ist `/chat` die Standard-Zielseite. Das Template enthält nur den Chat-Bereich: Nachrichtenlog, Eingabeformular und Statuszeile.

Die Chat-Historie in der Sidebar (`layout.html`: `#chat-history-list`, `#new-chat-btn`) wird global in `app.js` verwaltet; dieser Template-Body konzentriert sich auf den aktiven Gesprächsverlauf. Antworten des Assistenten werden clientseitig mit `marked` und `DOMPurify` gerendert (Vendor-Skripte im Block `vendor_scripts`).

Lesereihenfolge: Layout-Vererbung → `content` (Panel mit Log, Composer, Formular) → `vendor_scripts` (Markdown/Sanitizer).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `layout.html`; `/static/vendor/marked.min.js`, `/static/vendor/purify.min.js`
- **Wird genutzt von:** `backend/app/routes.py` — `chat_page` (`GET /chat`, `active_page="chat"`)
- **HTTP / UI / CLI:**
  - Seite: `GET /chat`
  - API (via JS): `GET /api/chats/{id}`, `POST /api/chat`, Chat-Historie über Sidebar-Endpoints
- **Daten:** SQLite `Chat`, `ChatMessage`; Session `customer_id` für Mandantenkontext

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `title` | Jinja-Block | Browser-Titel: „Chat · MARIS - Q/A Helper“ |
| `page_title` | Jinja-Block | Seitenüberschrift: „Chat“ |
| `content` | Jinja-Block | Chat-Panel mit Log und Composer |
| `vendor_scripts` | Jinja-Block | Zusätzliche Skripte vor `app.js`: Markdown-Rendering und HTML-Sanitisierung |

## Funktionen und Klassen

Keine — reines Markup; Chat-Logik in `app.js` (`initChatPage`).

## HTML / JS / CSS — zusätzliche Hinweise

- **extends:** `layout.html` — setzt `APP_BOOT.page = "chat"` und lädt `/static/app.js`
- **Page-Boot:** `initChatPage()` bei `APP_BOOT.page === "chat"`
- **Wichtige Element-IDs:**

| ID | Zweck |
|---|---|
| `chat-log` | Container für Chat-Bubbles (`aria-live="polite"`) |
| `chat-status` | Fehler-/Hinweisstatus unter dem Composer |
| `chat-form` | Submit-Formular für neue Nachrichten |
| `chat-input` | Textarea (Enter ohne Shift sendet) |
| `chat-submit` | Button „Senden“ |

- **Vendor-Block:** Überschreibt leeren Default in `layout.html`; Reihenfolge: `marked.min.js` → `purify.min.js` → (Layout) `app.js`
- **API-Aufrufe (JS):** `POST /api/chat` mit `{ message, chat_id? }`; Laden eines Verlaufs via `GET /api/chats/{chatId}`
- **CSS-Klassen:** `panel`, `chat-panel`, `chat-log`, `chat-composer`, `chat-form`, `bubble` (dynamisch)
