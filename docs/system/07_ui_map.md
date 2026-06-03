# 07 — UI-Karte (Seite → Code → API)

**Stand:** 2026-06-03

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
| `/` | — | — | Redirect `/chat` | — |

Basis: `layout.html` (Sidebar, Kunde, Chat-Historie, Admin-Nav).

---

## Wichtige API-Zuordnungen (Client)

| UI-Aktion | Endpoint |
|---|---|
| Kunde wechseln | `POST /api/session/customer` |
| Chat senden | `POST /api/chat` |
| Chat-Verlauf | `GET /api/chats`, `GET /api/chats/{id}` |
| KB Text | `POST /api/documents/text` |
| KB Upload | `POST /api/documents` |
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
| Kein Kunde gewählt | `#no-customer-banner`, `.page-content.disabled` |
| Global-Modus | Read-only Hinweis auf `/kb` |
| Upload/Fehler | `.status.error`, Badge `failed` |
| Leerer Chat | Platzhalter in `#chat-log` |

Planungsdetail: [`08_ui_ux_design.md`](../08_ui_ux_design.md) (aktualisiert)

---

## Betroffene Spiegel-Dateien

`templates/*.md`, `static/app.md`, `static/app.css` (in app.md), `routes.md`
