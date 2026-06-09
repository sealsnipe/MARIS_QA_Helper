# `backend/app/static/app.js`

**Quellpfad:** `backend/app/static/app.js`

## Zweck und logischer Aufbau

Clientseitige **Single-Page-Logik** für alle App-Views: IIFE liest `window.APP_BOOT`, stellt gemeinsame Helfer (`api`, Markdown, Status) bereit und initialisiert seitenabhängig Chat, KB, Admin-Wissen, Prompts, Benutzer und Kunden.

Lesereihenfolge: Boot-Variablen aus `APP_BOOT` → Utility-Funktionen → Sidebar/Kunde → Dokumenten-Rendering → Dropzone/Ingest → Seiten-Init (`initChatPage`, …) → Boot am Ende (Sync Kunde, `init*Page` nach `page`).

Datenfluss: Fast alle Aktionen gehen über `fetch` mit Session-Cookie (`credentials: "same-origin"`) an `/api/*`-Endpunkte in `routes.py`. 500er von `unhandled_exception_handler` liefern jetzt `{"error":"internal_error","ref":"..."}` (kein `detail` Leak); ref für Support-Logs (kein Parse von altem `detail` im Code gefunden).

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `window.APP_BOOT` (aus Jinja/`layout.html`): `page`, `globalCustomerId`, `customerLabels`, `isAdmin`, `activeCustomerId`, `activeCustomerName`
  - Vendor: `marked`, `DOMPurify` (optional, Fallback escaped Text)
- **Wird genutzt von:**
  - `layout.html` und abgeleitete Templates — `<script src="/static/app.js">`
- **HTTP / UI:** siehe Funktionen; zentral `api(path, options)`
- **DOM-IDs:** abgestimmt mit Templates (`chat-log`, `knowledge-scope`, `user-table-body`, …)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| IIFE | Modulscope | Kapselt gesamte Client-Logik |
| `boot` | Objekt | `window.APP_BOOT \|\| {}` |
| `page` | String | Aktuelle View: `chat`, `kb`, `admin_knowledge`, `admin_prompts`, `admin_users`, `customers` |
| `globalCustomerId` | String | ID des Global-Mandanten (Default `"global"`) |
| `customerLabels` | Objekt | Map `customer_id → name` |
| `isAdmin` | Boolean | Admin-Navigation |
| `activeCustomerId` / `activeCustomerName` | String | Session-Mandant (mutierbar) |
| `activeChatId` | String | Aktuelle Chat-ID aus URL `?c=` |
| `ICON_EDIT` / `ICON_TRASH` | String (SVG HTML) | Icons in Benutzertabelle |

## Funktionen und Klassen

### `api(path, options = {})`

**Beschreibung:** JSON/Form-`fetch`-Wrapper mit Fehlerbehandlung.

**Parameter / Rückgabe:** URL-Pfad, Fetch-Optionen. Setzt `Content-Type: application/json` außer bei `FormData`. Wirft `Error` mit `code`, `detail`, `status` bei `!response.ok`.

**Ablauf / lokale Variablen:** `payload` — parsed JSON bei passendem Content-Type.

---

### `isGlobalCustomer()`

**Beschreibung:** Prüft, ob `activeCustomerId === globalCustomerId`.

---

### `escapeHtml(value)`

**Beschreibung:** Escaped HTML-Sonderzeichen für sichere Textausgabe.

---

### `showStatus(el, message, kind = "")`

**Beschreibung:** Setzt Text und CSS-Klasse auf Status-Elemente (`status`, optional `error`/`ok`).

---

### `renderMarkdown(text)`

**Beschreibung:** Markdown → sanitisiertes HTML via `marked` + `DOMPurify`; Fallback Plain-Text.

**Optionen:** GFM, `breaks: true`, keine Header-IDs.

---

### `setBubbleContent(bubble, text)`

**Beschreibung:** Fügt `.markdown-body` mit gerendertem HTML in Chat-Blase ein.

---

### `setCustomerUiEnabled(enabled)`

**Beschreibung:** Auf `chat`/`kb`: blendet `#no-customer-banner` ein/aus, deaktiviert `#page-content`, aktualisiert KB-Namen-Suffix.

---

### `syncActiveCustomerFromSelect()`

**Beschreibung:** Liest `#customer-select` (SELECT oder hidden input) in `activeCustomerId` / `activeCustomerName`.

---

### `switchCustomer(customerId)` (async)

**Beschreibung:** `POST /api/session/customer`, dann Reload ohne `?c`-Parameter.

---

### `setActiveChatInUrl(chatId)`

**Beschreibung:** Aktualisiert Query `c` per `history.replaceState` (nur Seite `chat`).

---

### `refreshChatHistory()` (async)

**Beschreibung:** Lädt `/api/chats`, rendert Sidebar-Liste mit Link und Löschen-Button.

**Ablauf:** Leerzustände, Fehleranzeige; Delete ruft `DELETE /api/chats/{id}`.

---

### `initChatSidebar()`

**Beschreibung:** „Neuer Chat“-Button, Kunden-Select-Change → `switchCustomer`, initial Event-Listener.

---

### `renderDocuments(documents, listEl, countEl, emptyEl, deletePath, options = {})`

**Beschreibung:** Baut `<li class="doc-item">`-Liste mit Meta und optionalen Aktionen (Löschen, Admin-Bearbeiten).

**Optionen:** `readOnly`, `showCustomer` (Badge mit Mandantenname), `adminEdit: { basePath, onRefresh }` — zeigt Stift-Icon, öffnet inline Edit-Panel.

**Delete:** `DELETE` auf `deletePath/{id}`, danach passender Refresh.

---

### `openAdminDocumentEditor(docId, basePath, listEl, onRefresh)` (async)

**Beschreibung:** Lädt `GET {basePath}/{id}`, rendert Inline-Panel (Titel, Textarea, Speichern/Abbrechen). PUT bei Speichern, danach `onRefresh`. Hinweis bei `from_file`.

---

### `closeAllDocEditPanels(listEl)`

**Beschreibung:** Entfernt alle `.doc-edit-row`-Panels aus der Dokumentliste.

---

### `setKbReadOnlyMode(readOnly)`

**Beschreibung:** Blendet Ingest-Form aus, zeigt Read-only-Banner, passt Leertext an.

---

### `refreshKbDocuments()` (async)

**Beschreibung:** `GET /api/documents` → `setKbReadOnlyMode` + `renderDocuments` für Endnutzer-KB.

---

### `refreshAdminDocuments(scope = "global")` (async)

**Beschreibung:** Lädt Admin-Dokumente global oder pro Mandant (`/api/admin/...`); übergibt `adminEdit` an `renderDocuments` für Bearbeiten-Icons.

---

### `knowledgeScopeLabel(scope)`

**Beschreibung:** Anzeigename für KB-Scope (`"Global"` oder Label aus `customerLabels`).

---

### `initAdminNav()`

**Beschreibung:** Toggle für `#admin-nav-group` / `#admin-nav-toggle`, `aria-expanded`.

---

### `setupDropzone(dropzone, fileInput, fileLabel, onSelect, isFileSelected)`

**Beschreibung:** Klick, Tastatur, Drag&Drop und **Strg+V** auf der Dropzone für Dateiauswahl; ruft `onSelect(file)` auf.

---

### `fileFromClipboard(clipboardData)`

**Beschreibung:** Liest erste Datei aus der Zwischenablage; Screenshots (`image/*`) werden als `eingefuegtes-bild-{timestamp}.png|jpg|…` benannt.

---

### `bindIngestForm({ form, … })`

**Beschreibung:** Generisches Einpflege-Formular: Validierung, optional **Inspect** (`POST …/inspect`), **Vision-Modal** mit Bild-Checkboxen, Upload mit `process_images` + `transcribe_image_ids`, Fehlercodes, Reset bei Erfolg.

**Lokale Variablen:** `selectedFile`, `fileInspection`, `warningEl`, `INSPECTABLE_FILE_PATTERN`.

**Vision-Flow:** `askImageVisionChoice` → `{ action: "transcribe"|"text"|"cancel", selectedIds }`.

**Paste:** zusätzlicher `paste`-Listener auf `form` — Strg+V im Formular (auch aus Textarea-Kontext wenn Clipboard Datei enthält).

---

### `ensureImageVisionModal()` / `askImageVisionChoice(inspection)`

**Beschreibung:** Modal mit Header (Titel + „Alle markieren“ / „Alle abwählen“ Buttons), Thumbnail-Grid und Checkboxen; Buttons „Ausgewählte transkribieren“, „Ohne OCR einpflegen“, „Abbrechen“. Die Select-Buttons togglen alle sichtbaren Bild-Checkboxen.

---

### `ensureImageLightbox()` / `openImageLightbox(url, label)`

**Beschreibung:** Vollbild-Vorschau extrahierter Bilder im Admin-Editor.

---

### `bindDocumentImagePreviews(container)`

**Beschreibung:** Klick auf `.doc-edit-image-item` öffnet Lightbox.

---

### `buildSourcesPopover(sources)`

**Beschreibung:** Erzeugt „Quellen“-Button mit Tooltip-Liste (`[n] title · Textabschnitt`).

---

### `initChatPage()`

**Beschreibung:** Chat-Hauptlogik: Verlauf laden, senden, Markdown-Bubbles.

#### `scrollChatToBottom()`

Scrollt `#chat-log` ans Ende (`requestAnimationFrame`).

#### `appendBubble(role, text, sources = null)`

Erstellt `.bubble.{role}`; Assistant mit Markdown und optional Quellen-Popover.

#### `renderChatLog(messages)`

Leert Log, rendert User/Assistant-Nachrichten aus API.

#### `loadChat(chatId)` (async)

`GET /api/chats/{id}` → setzt `activeChatId`, rendert Messages, refresht Historie.

**Events:** Form-Submit → `POST /api/chat`; Enter ohne Shift sendet; initialer Load wenn `?c=` gesetzt.

---

### `initKbPage()`

**Beschreibung:** Endnutzer-Wissensbasis: Read-only bei Global, `bindIngestForm` auf `/api/documents`, initial `refreshKbDocuments`.

---

### `initAdminKnowledgePage()`

**Beschreibung:** Admin-KB mit Scope-Select global/Kunde.

#### `currentScope()`

Liest `#knowledge-scope` (Default `"global"`).

#### `updateScopeUi()`

Aktualisiert Label und Hinweistext je Scope.

#### `refreshScopeDocuments()` (async)

Ruft `refreshAdminDocuments(currentScope())`.

**Ingest:** dynamischer `apiPath` global vs. `/api/admin/customers/{scope}/documents`.

---

### `initAdminPromptsPage()`

**Beschreibung:** System-Prompt bearbeiten.

#### `loadPrompt()` (async)

`GET /api/admin/system-prompt` mit optionalem `customer_id` Query.

**Submit:** `PUT /api/admin/system-prompt` mit `{ customer_id, content }`.

---

### `renderCustomerCheckboxes(container, customers, selectedIds, namePrefix)`

**Beschreibung:** Checkbox-Liste für Mandantenzuordnung (Create/Edit User).

---

### `readCustomerCheckboxValues(container, namePrefix)`

**Beschreibung:** Sammelt checked values für gegebenes `name`-Attribut.

---

### `initUsersPage()`

**Beschreibung:** Admin-Benutzerverwaltung (Tabelle, Inline-Edit, Create).

#### `customerBadges(ids)`

HTML für Slug-Badges mit Tooltip-Namen.

#### `renderUsers(users)`

Baut Tabellenzeilen + versteckte Edit-Zeilen pro User.

#### `loadUsers()` (async)

`GET /api/admin/users` → Checkboxen + Tabelle.

**Delegation:** Edit/Save/Cancel/Delete auf `#user-table-body`; PATCH/DELETE `/api/admin/users/{id}`; Create-Form POST.

---

### `initCustomersPage()`

**Beschreibung:** Admin-Mandantenverwaltung (CRUD in Tabelle).

#### `renderCustomers(customers)`

Tabellenzeilen mit Inline-Edit für ID und Name.

#### `loadCustomers()` (async)

`GET /api/admin/customers`.

**Events:** Edit/Save/Cancel/Delete; PATCH mit optionalem Slug-Wechsel (`id` im Body); Validierung `/^[a-z0-9_-]+$/`; Create POST.

---

## Page-Boot (IIFE-Ende)

Nach Definition aller Init-Funktionen:

1. `syncActiveCustomerFromSelect()`
2. `setCustomerUiEnabled(Boolean(activeCustomerId))`
3. `initChatSidebar()`; `refreshChatHistory()`
4. `isAdmin` → `initAdminNav()`
5. Abhängig von `page`: `initChatPage`, `initKbPage`, `initAdminKnowledgePage`, `initAdminPromptsPage`, `initUsersPage`, `initCustomersPage`

## HTML / JS — zusätzliche Hinweise

| `APP_BOOT.page` | Init-Funktion | Haupt-APIs |
|---|---|---|
| `chat` | `initChatPage` | `/api/chat`, `/api/chats` |
| `kb` | `initKbPage` | `/api/documents` |
| `admin_knowledge` | `initAdminKnowledgePage` | `/api/admin/documents`, `/api/admin/customers/…/documents` |
| `admin_prompts` | `initAdminPromptsPage` | `/api/admin/system-prompt` |
| `admin_users` | `initUsersPage` | `/api/admin/users` |
| `customers` | `initCustomersPage` | `/api/admin/customers` |

Globale Mandantenumschaltung: `#customer-select` → `POST /api/session/customer`.

---

# `backend/app/static/app.css`

**Quellpfad:** `backend/app/static/app.css`

*(In dieser Datei mit dokumentiert — Basisname-Kollision mit `app.js`, siehe `docs/DOCUMENTATION_RULES.md` / INDEX.)*

## Zweck und logischer Aufbau (CSS)

Globales Dark-Theme-Stylesheet: Sidebar, Main, Chat, KB, Admin, Login. Eingebunden in `layout.html`; Klassen von Templates und `app.js`.

## Abhängigkeiten und Traces (CSS)

- **Wird genutzt von:** `layout.html`, App-Templates, `app.js`
- **HTTP:** `/static/app.css`

## CSS-Variablen (`:root`)

`--bg`, `--surface`, `--border`, `--text`, `--text-muted`, `--accent`, `--danger`, `--ok`, `--radius`, `--gap`, `--font`, `color-scheme: dark`

## Komponenten-Sektionen (Auszug)

| Bereich | Selektoren |
|---|---|
| Layout | `.app-layout`, `.sidebar`, `.main-area`, `.panel` |
| Navigation | `.nav-link`, `.nav-group`, `.chat-history-list` |
| Chat | `body.page-chat`, `.chat-log`, `.bubble`, `.sources-popover` |
| Forms/KB | `.ingest-form`, `.dropzone`, `.image-vision-modal`, `.image-vision-header`, `.image-vision-select-actions`, `.image-vision-grid`, `.doc-edit-images`, `.image-lightbox`, `.doc-list`, `.status` |
| Admin | `.customer-table`, `.user-customer-checkboxes`, `.icon-btn` |
| Login | `.login-card`, `.login-brand-banner` |
| Utils | `.hidden`, `.muted`, `button.secondary/danger/small` |

