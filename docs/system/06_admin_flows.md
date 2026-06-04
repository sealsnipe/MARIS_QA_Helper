# 06 — Admin-Flows

**Stand:** 2026-06-05

---

## Navigation (nur `is_admin`)

```text
Einstellungen
  ▾ Administration
      Kunden           → /admin/customers
      Wissensdatenbanken → /admin/knowledge
      Systemprompts    → /admin/prompts
      User
        Benutzer       → /admin/users
        Rollen         → /admin/roles
      Keys             → /admin/keys
```

`/admin` → Redirect `/admin/customers`. Nicht-Admins → `/chat`.

Spiegel: `templates/layout.md`, `static/app.md` (`initAdminNav`)

---

## Sidebar-Kunde auf Admin-Seiten

| Seite | Mandanten-Bezug |
|---|---|
| Kunden, User, Rollen, Keys | **Global** — Sidebar-Kunde hat keine Auswirkung auf Seiteninhalt |
| Wissensdatenbanken, Systemprompts | **Ja** — Sidebar sync mit Scope-Dropdown (global vs. Mandant) |
| Chat, KB (Nutzer) | **Ja** — Kunde Pflicht |

**Admins** sehen in der Sidebar **Global + alle aktiven Mandanten** (unabhängig von direkten `user_customers`-Zeilen). Normale Nutzer nur zugewiesene Mandanten.

Details: [`07_ui_map.md`](./07_ui_map.md#sidebar-kunde-customer_nav_mode)

---

## Kunden-Verwaltung

| Aktion | API | Backend |
|---|---|---|
| Liste | `GET /api/admin/customers` | `list_tenant_customers` |
| Anlegen | `POST /api/admin/customers` | `create_tenant_customer` — vergibt Admins automatisch Membership |
| Name ändern | `PATCH …/{id}` `{name}` | `update_tenant_customer` |
| **Slug umbenennen** | `PATCH …/{id}` `{id, name?}` | `rename_tenant_customer` |
| Deaktivieren | `DELETE …/{id}` | `deactivate_tenant_customer` (soft: `active=0`) |

### Slug-Rename (kritisch)

Reihenfolge in `rename_tenant_customer`:

1. Qdrant: `copy_collection(old → new)`, Payload `customer_id` aktualisieren
2. SQLite: neue `customers`-Zeile, UPDATE aller FKs (`documents`, `chunks`, `user_customers`, `chat_sessions`, `system_prompts`)
3. Qdrant: alte Collection löschen
4. FS: `data/uploads/{old}/` → `{new}/` (best effort)

Bei SQLite-Fehler: Rollback + neue Qdrant-Collection entfernen.

Spiegel: `customers.md`, `qdrant_store.md`, `templates/customers.md`

---

## Benutzer-Verwaltung

| Aktion | API | Backend |
|---|---|---|
| Liste + Mandanten | `GET /api/admin/users` | `list_admin_users`, `list_assignable_customers` |
| Anlegen | `POST /api/admin/users` | `create_admin_user` |
| Bearbeiten | `PATCH /api/admin/users/{id}` | `update_admin_user` |
| Deaktivieren | `DELETE /api/admin/users/{id}` | `deactivate_admin_user` |

Schutz: Admin kann sich nicht selbst deaktivieren / Admin-Recht entziehen.

Spiegel: `users_admin.md`, `templates/admin_users.md`

---

## Wissensdatenbank (Admin)

- **Global:** `GET/POST/DELETE /api/admin/documents`, **`GET/PUT /api/admin/documents/{id}`**
- **Pro Mandant:** `…/api/admin/customers/{id}/documents`, **`GET/PUT …/documents/{doc_id}`**
- **Bearbeiten:** Admin-UI lädt Volltext → Editor → Speichern triggert Re-Index (gleiche `document_id`)

Scope-UI in `admin_knowledge.html` — Dropdown wählt global vs Tenant.

---

## Systemprompts

- `GET/PUT /api/admin/system-prompt?customer_id=` (null = global)
- Effektiver Chat-Prompt: global + mandantenspezifisch + Hints (`system_prompts.get_effective_system_prompt`)

Spiegel: `system_prompts.md`, `templates/admin_prompts.md`

---

## Betroffene Spiegel-Dateien

`customers.md`, `users_admin.md`, `routes.md`, `templates/customers.md`, `templates/admin_*.md`, `static/app.md`
