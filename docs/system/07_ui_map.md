# 07 — UI-Karte (Seite → Code → API)

**Stand:** 2026-06-05

---

## HTML-Routen

| URL | Template | `APP_BOOT.page` | JS-Init | Auth |
|---|---|---|---|---|
| `/login` | `login.html` | — | — | öffentlich |
| `/chat` | `chat.html` | `chat` | `initChatPage` | User + Kunde |
| `/kb` | `kb.html` | `kb` | `initKbPage` | User + Kunde; Admin → Redirect `/admin/knowledge` |
| `/admin/customers` | `customers.html` | `customers` | `initCustomersPage` | Admin |
| `/admin/knowledge` | `admin_knowledge.html` | `admin_knowledge` | `initAdminKnowledgePage` | Admin |
| `/admin/prompts` | `admin_prompts.html` | `admin_prompts` | `initAdminPromptsPage` | Admin |
| `/admin/users` | `admin_users.html` | `admin_users` | `initUsersPage` | Admin |
| `/admin/roles` | `admin_roles.html` | `admin_roles` | `initRolesPage` | Admin |
| `/admin/keys` | `admin_keys.html` | `admin_keys` | `initKeysPage` | Admin |
| `/tools/knowledge-center/submit` | `tools/knowledge_center_submit.html` | `tools_kc_submit` | `initKnowledgeCenterSubmitPage` | User |
| `/tools/knowledge-center` | `tools/knowledge_center_content.html` | `tools_kc_content` | `initKnowledgeCenterContentPage` | Admin (User → Redirect Submit) |
| `/tools/knowledge-center/sources` | `tools/knowledge_center_sources.html` | `tools_kc_sources` | `initKnowledgeCenterSourcesPage` | Admin |
| `/tools/bild-zu-text` | `tools/bild_zu_text.html` | `tools_bild_zu_text` | `initImageToTextTool` | User (scoped) |
| `/` | — | — | Redirect `/chat` | — |

Basis: `layout.html` (Sidebar, Kunde, Chat-Historie, Admin-Nav).

---

## Sidebar-Kunde (`customer_nav_mode`)

Das Dropdown **Kunde** in der Sidebar gilt sitzungsweit, wirkt aber **seitenabhängig**:

| Modus | Seiten | Verhalten |
|---|---|---|
| **`scoped`** | `/chat`, `/kb`, `/tools/bild-zu-text` | Kunde **Pflicht**; Wechsel → Session + Seiten-Reload; `#no-customer-banner` wenn leer |
| **`admin_scoped`** | `/admin/knowledge`, `/admin/prompts` | Sidebar steuert den Mandanten-Kontext (sync mit Scope-Dropdown auf der Seite); kein Full-Reload |
| **`global`** | `/admin/customers`, `/admin/users`, `/admin/roles`, `/admin/keys`, `/tools/knowledge-center`, `/tools/knowledge-center/submit` | Kein Mandanten-Bezug der Sidebar für Seiteninhalt |

Admins ohne direkte `user_customers`-Zeilen sehen **Global + alle aktiven Mandanten** in der Sidebar (nicht nur Global).

Implementierung: `routes.customer_nav_mode`, `APP_BOOT.customerNavMode`, `app.js` (`pageNeedsCustomer`, `syncAdminPageScopeFromSidebar`).

---

## Wichtige API-Zuordnungen (Client)

| UI-Aktion | Endpoint |
|---|---|
| Kunde wechseln | `POST /api/session/customer` |
| Chat senden | `POST /api/chat` |
| Chat-Verlauf | `GET /api/chats`, `GET /api/chats/{id}` |
| KB Text | `POST /api/documents/text` |
| KB Inspect | `POST /api/documents/inspect` |
| KB Upload | `POST /api/documents` (+ `process_images`, `transcribe_image_ids`) |
| KB Bild | `GET /api/documents/{id}/images/{image_id}` |
| KB löschen | `DELETE /api/documents/{id}` |
| Admin Kunden CRUD | `/api/admin/customers` |
| Admin User CRUD | `/api/admin/users` |
| Admin KB | `/api/admin/documents`, `/api/admin/customers/{id}/documents` |
| Admin Prompt | `/api/admin/system-prompt` |

Zentraler Client: `app.js` — `api()`, `showStatus()`, Markdown via `marked` + `DOMPurify`.

---

## Zustände (UX)

| Zustand | UI |
|---|---|
| Kein Kunde gewählt (nur `scoped`) | `#no-customer-banner`, `.page-content.disabled` |
| Global-Modus | Read-only Hinweis auf `/kb` |
| Admin global (Keys/User/Rollen/Kunden) | Sidebar-Hinweis „Gilt nicht für diese Seite“ |
| Upload/Fehler | `.status.error`, Badge `failed` |
| Leerer Chat | Platzhalter in `#chat-log` |

Planungsdetail: [`08_ui_ux_design.md`](../08_ui_ux_design.md) (aktualisiert)

---

## Betroffene Spiegel-Dateien

`templates/*.md`, `static/app.md`, `static/app.css` (in app.md), `routes.md`
