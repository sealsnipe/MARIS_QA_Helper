# 15 — Implementierungsstatus (Plan vs Ist)

**Stand:** 2026-06-04

---

## Zweck

Abgleich zwischen **Planungsdocs** (`docs/01–14`, Stand teils 2026-06-02) und **aktueller Codebasis**. Bei Widerspruch gilt der Code + [`docs/system/`](../system/00_README.md) + Spiegel `docs/docs/`.

---

## MVP-Kern — erfüllt

| Feature | Plan | Ist |
|---|---|---|
| Login Session Argon2 | `07` | ✅ |
| Mandant pro Session | `03`, `07` | ✅ |
| KB Text + Upload | `02`, `05` | ✅ |
| RAG-Chat mit Quellen | `06` | ✅ |
| Qdrant pro Kunde | `04` | ✅ |
| Tenant-Isolation Tests | `10` | ✅ |

---

## Nach MVP implementiert (Plan veraltet)

| Feature | Plan sagte | Ist (2026-06-03) |
|---|---|---|
| **Admin-UI Kunden** | Phase 4 / Script only (`14` §2) | ✅ `/admin/customers`, CRUD + **Slug-Rename** |
| **Admin-UI User** | nicht in MVP | ✅ `/admin/users`, CRUD, Mandantenzuordnung |
| **Admin KB getrennt** | eine Hauptseite | ✅ `/admin/knowledge` (global + pro Mandant) |
| **Admin Prompts** | — | ✅ `/admin/prompts` |
| **Navigation** | Header eine Seite | ✅ Sidebar: Chat, KB, Admin-Untermenü |
| **Chat-Sessions** | ein Verlauf | ✅ mehrere Chats pro Mandant, Sidebar-Historie |
| **Global-Mandant** | — | ✅ `global` + scoped multi-KB-Suche |
| **Admin KB bearbeiten** | — | ✅ GET/PUT Admin-Dokument, Re-Index, `source_text` |
| **Slug-Rename Migration** | Entscheidungsvorlage `14` | ✅ SQLite + Qdrant + Uploads |
| **Vision-OCR / Bilder** | Roadmap | ✅ Inspect, selektive OCR, inline DOCX, Thumbnails, Strg+V |
|| **UI Tools-Sektion** | — | ✅ Sidebar "Tools" (zwischen Chats und Einstellungen) mit erstem Tool "Bild zu Text" (Strg+V, Vision-OCR, Text-Output + Kopieren) |

---

## Dokumentation — Stand

| Ebene | Status |
|---|---|
| Planung `01–14` | vorhanden, **teilweise aktualisiert** (05, 08, 11, 14) |
| Spiegel `docs/docs/` | ~90+ Dateien (file-per-file) |
| Querschnitt `docs/system/` | ✅ 00–11 |
| Regelwerk | `DOCUMENTATION_RULES.md` inkl. Ebene 3 |

---

## Roadmap (unverändert out of scope)

- Jira-Import
- SSO / OIDC
- Self-Service Sign-up
- Hard-Delete / Compliance-Aufbewahrung

Siehe [`12_roadmap.md`](./12_roadmap.md)

---

## Empfohlene Planungsdoc-Updates bei nächster Änderung

| Doc | Grund |
|---|---|
| `03_architecture.md` | Admin-Komponenten, Chat-Sessions |
| `05_api_specification.md` | Admin + Chat APIs |
| `08_ui_ux_design.md` | Sidebar, Admin-Seiten |
| `14_customer_administration.md` | Status „implementiert“ |

Diese Updates wurden 2026-06-03 **begonnen** — Details in den jeweiligen Dateien prüfen.
