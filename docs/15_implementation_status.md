# 15 — Implementierungsstatus (Plan vs Ist)

**Stand:** 2026-06-09 (Review 2026-06-09 + 7 Aufgaben umgesetzt; siehe `docs/orchestration/2026-06-09-review-und-implementationsplan.md` (archiviert nach _old))

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
| **UI Tools-Sektion** | — | ✅ Sidebar "Tools" mit "Bild zu Text" |
| **Knowledge Center** | — | ✅ Content vorschlagen (User), Dashboard + Sources (Admin), KI-Presets, Diff-Review |
| **Duplikat-Erkennung (Stufe 1)** | Phase 3 | ✅ Exakter `content_sha256`, Inspect-Warnung, Upload mit Bestätigung |
| **Duplikat-Erkennung (Stufe 2)** | Phase 3 | ✅ Document-Fingerprint in Qdrant, `similar[]` im Inspect, UI-Warnung |

---

## Dokumentation — Stand

| Ebene | Status |
|---|---|
| Planung `01–14` | vorhanden, **teilweise aktualisiert** (05, 08, 11, 14) |
| Spiegel `docs/docs/` | ~115+ Dateien (file-per-file; alle 25 fehlenden nach Review 2026-06 nachgezogen; INDEX komplett) |
| Review 2026-06-09 + Impl-Plan | 7 Aufgaben (F1–F6) einzeln committed, Tests+Tenant+ Doku-Spiegel nach jeder; CI, Rate-Limit, no-leak 500, pdfimages cleanup, DB-Token, Image-Heuristik-Fix; InMemory copy fix (kein move mehr); Secrets-at-rest doku; Status aktualisiert. Plan nach _old verschoben (ERLEDIGT). |
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
| `03_architecture.md` | ✅ §7 Repo-Struktur + Komponenten (Review-Sync 2026-06) |
| `05_api_specification.md` | Admin + Chat + Integration APIs (teilweise aktuell; bei Bedarf vertiefen) |
| `08_ui_ux_design.md` | Sidebar, Admin-Seiten, Tools (teilweise) |
| `14_customer_administration.md` | Status „implementiert“ |

**Review 2026-06:** `PROJECT_STANDARDS.md` neu, 25 Spiegel + `docs/docs/INDEX.md` + `system/09` + `03 §7` + `15` aktualisiert (A-Pfad, kein Refactor). Siehe `reviews/2026-06-05-project-review.md`.

Diese Updates wurden 2026-06-03 **begonnen** und im Review-Branch finalisiert — Details in den jeweiligen Dateien prüfen.

