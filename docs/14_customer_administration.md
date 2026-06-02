# 14 — Kunden-Administration: Ausarbeitung für Projektmanagement

**Stand:** 2026-06-02 · **Status:** Entscheidungsvorlage (nicht MVP-bindend bis PM-Freigabe)  
**Adressat:** Projektmanager / Product Owner  
**Autor:** Engineering (Coding-Agent)  
**Bezug:** `02` (Persona P3 „Achim“), `04` §1.2/§1.3, `07` §5, `12` Phase 4

---

## 1. Anlass

Für den produktiven Einsatz sind **vier konkrete Kunden** vorgesehen:

| # | Anzeigename (Vorschlag) | Vorschlag `customer_id` (Slug) | Hinweis |
|---|---|---|---|
| 1 | BG Ludwigshafen | `bg-ludwigshafen` | Berufsgenossenschaft |
| 2 | BG Frankfurt | `bg-frankfurt` | Berufsgenossenschaft |
| 3 | Detmold Lippe | `detmold-lippe` | |
| 4 | Katholische Kliniken Rhein Ruhr | `kkrr` *oder* `katholische-kliniken-rhein-ruhr` | Kurz-Slug vs. lesbarer Lang-Slug — **PM-Entscheid** |

Der Slug (`customer_id`) ist **dauerhaft** und bildet u.a. den Qdrant-Collection-Namen (`kb_{customer_id}`).
Regel laut Spec: nur `[a-z0-9_-]+`, keine Umlaute/Leerzeichen.

**Frage an PM:** Slugs und Anzeigenamen final bestätigen (Tabelle oben).

### PM-Entscheid (2026-06-02, FINAL)

Es gelten die **internen Kürzel** als Slug (lowercase). Slugs sind **final und permanent**:

| # | Anzeigename | `customer_id` (final) | Collection |
|---|---|---|---|
| 1 | BG Ludwigshafen | `bglu` | `kb_bglu` |
| 2 | BG Frankfurt | `bguf` | `kb_bguf` |
| 3 | Detmold Lippe | `kkld` | `kb_kkld` |
| 4 | Katholische Kliniken Rhein Ruhr | `krh` | `kb_krh` |

Weitere Festlegungen:
- **Vorgehen:** Option A (Script-Seed) jetzt; Admin-API/UI = Phase 4 (Option D-Pfad). **Kein Admin-Code in M3–M7.**
- **Demo-Kunden** `acme`/`globex`: **nur in Test-Fixtures**, nicht im Produktiv-Seed.
- **Seed-Nutzer (Prototyp):** `sealsnipe@gmail.com` allen vier Kunden zugeordnet (Mandantenwechsel testbar); zusätzlich Testnutzer für `acme`/`globex`.
- **Prototyp-Inhalte:** **sanitisiert/synthetisch** — **keine Echtdaten** vor Datenresidenz-/DSGVO-Klärung (OpenAI=US-Verarbeitung; BG/Klinik = sensibel). Gate dafür in `12` Phase 4/5.
- **Delete:** im MVP Soft-Delete; Hard-Delete/Aufbewahrung später (Compliance).

---

## 2. Ist-Zustand (MVP, Stand M2)

| Thema | Heute im MVP |
|---|---|
| Kunden anlegen | **Nur** per Script `scripts/seed_customers.py` (idempotent) |
| Nutzer anlegen | **Nur** per Script `scripts/seed_users.py` (+ `user_customers`) |
| UI für Administration | **Nein** — bewusst out of scope (`07`, `12` Phase 4) |
| Demo-Kunden | `acme`, `globex` (Isolationstests, Abnahme) |
| API für Endnutzer | `GET /api/customers` (nur **lesen**, nur erlaubte Kunden) |
| Self-Service | Kein Sign-up, kein „Kunde anlegen“ durch Support-Nutzer |

Persona **P3 „Achim“ (Betreiber/Admin)** ist in `02` definiert; der MVP erfüllt deren Erfolg über **Script + Docker**, nicht über eine Admin-Oberfläche.

---

## 3. Warum Administration (über Seed hinaus) relevant wird

Sobald echte Kunden live gehen, braucht der Betrieb wiederkehrend:

1. **Neuen Kunden anlegen** (Name + Slug, ohne Deployment)
2. **Nutzer dem Kunden zuordnen** (wer sieht welchen Mandanten?)
3. **Optional: Kunde deaktivieren/löschen** (Offboarding, DSGVO)
4. **Nachvollziehbarkeit** — wer hat wann welchen Kunden angelegt?

Seed-Scripts reichen für **Erstinbetriebnahme** und **Dev/Test**, skaliieren aber schlecht für laufenden Betrieb ohne Ops-Know-how.

---

## 4. Konsequenzen bei „Kunde anlegen“ (technische Kette)

Jeder neue Kunde löst **mehrere Systeme** aus — nicht nur eine SQLite-Zeile:

```text
Admin legt Kunden an (Slug + Anzeigename)
  │
  ├─► SQLite `customers`          → 1 Row (id=slug, name=...)
  ├─► SQLite `user_customers`     → mindestens 1 Nutzer muss zugeordnet werden, sonst sieht niemand den Kunden
  ├─► Qdrant `kb_{slug}`          → Collection **lazy** bei erster Ingestion (ensure_collection)
  ├─► Session                     → bestehende Nutzer: kein auto-active Kunde, bis Auswahl/Zuordnung
  ├─► `./data/uploads/{slug}/`    → entsteht bei erstem Datei-Upload
  └─► Tenant-Isolation            → alle späteren Docs/Chat laufen nur gegen kb_{slug}
```

### 4.1 Was **nicht** automatisch passiert

- Keine KB-Inhalte — leerer Kunde ist normal
- Keine Nutzer-Zuordnung — **ohne** `user_customers` → 403 / leere Kundenliste
- Keine Qdrant-Collection — erst bei erster erfolgreicher Ingestion

### 4.2 Slug-Wechsel nachträglich

**Praktisch unmöglich ohne Migration:** `customer_id` ist Primary Key, referenziert in `documents`, `chunks`, Qdrant-Payload und Collection-Name.  
→ Slug beim Anlegen **final** klären (PM + Fachbereich).

### 4.3 Kunde „löschen“

| Aktion | SQLite | Qdrant | Uploads | Risiko |
|---|---|---|---|---|
| Soft-Delete Kunde (neu) | Flag `active=0` | Collection behalten | behalten | Daten bleiben, kein Zugriff |
| Hard-Delete | Rows + FK-Kaskade | `delete collection kb_{slug}` | Ordner löschen | **irreversibel**, DSGVO-relevant |
| Nur Zuordnung entfernen | `user_customers` weg | unverändert | unverändert | Kunde „orphan“, Daten bleiben |

**PM-Entscheid:** Soft vs. Hard Delete, Aufbewahrungsfristen.

### 4.4 Sicherheit / Mandantentrennung (Invariant — bleibt)

- `customer_id` **nie** aus Client-Body übernehmen (nur Session + `user ∈ customer`)
- Admin darf **keinen** Shortcut schaffen, der fremde Collections anspricht
- Neue Admin-Endpoints müssen **eigene Rolle** haben (nicht jeder Login-Nutzer)

---

## 5. Optionen für die PM-Entscheidung

### Option A — Script-only (Status quo+, empfohlen für **sofortigen** Go mit M3–M7)

**Was:** Vier produktive Kunden + Zuordnungen in `seed_customers.py` / `seed_users.py` (oder separates `seed_customers_production.py`). Demo `acme`/`globex` bleiben für Tests.

| Pro | Contra |
|---|---|
| Kein Scope-Sprung, M3–M7 unverändert | Jede Änderung braucht Script + ggf. Container-Exec |
| Passt zu `11` §6 Betrieb | Kein Self-Service für Achim |
| Geringes Risiko für Tenant-Bugs | |

**Aufwand:** ~0,5 h (Slugs bestätigen, Seed erweitern, einmal ausführen)

---

### Option B — Minimal Admin-API (ohne UI)

**Was:** Geschützte Endpoints nur für Rolle `admin`:

- `POST /api/admin/customers` — Slug + Name anlegen (Validierung)
- `POST /api/admin/users` — Nutzer + Passwort + Kundenliste
- `PATCH /api/admin/user-customers` — Zuordnung pflegen

| Pro | Contra |
|---|---|
| Kein UI-Bau, curl/Postman/Internes Tool | Braucht **RBAC** (`users.role`) — heute nicht im MVP |
| Betrieb ohne Git/SSH | Neues Sicherheitsmodell, Tests, Review |

**Aufwand:** ~2–3 Tage (Rolle, Endpoints, Tests, Doku) — **eigener Meilenstein**, nicht in M3–M7 eingeplant

---

### Option C — Admin-UI (Phase 4 laut `12`)

**Was:** Web-Oberfläche: Kunden CRUD, Nutzer CRUD, Zuordnungen, optional Audit-Log.

| Pro | Contra |
|---|---|
| P3 „Achim“ bedienbar ohne Terminal | Größter Scope; SSO/Compliance oft gewünscht |
| Skaliert für viele Kunden | Overlap mit Phase 4 (SSO, Audit) |

**Aufwand:** ~1–2 Wochen — **nach** MVP-Abnahme sinnvoll

---

### Option D — Hybrid (Empfehlung Engineering für **Projektverlauf**)

| Phase | Maßnahme |
|---|---|
| **Jetzt (M3–M7)** | Option A: Seed mit 4 echten Kunden + Demo-Kunden für Tests |
| **Nach Abnahme** | Option B oder C je nach Betriebsmodell (intern vs. Kunden-Self-Service) |

---

## 6. Blockiert das den weiteren Build (M3)?

**Nein.**

| Meilenstein | Abhängigkeit von Admin-UI |
|---|---|
| **M3** Ingestion (Text, Qdrant, Embeddings) | Kunden müssen in DB **existieren** — reicht per Seed |
| **M4** Upload | gleich |
| **M5** Agent/Chat | gleich |
| **M6** UI | Kundenauswahl aus `GET /api/customers` — unabhängig von Admin |
| **M7** Isolation-Tests | Demo `acme`/`globex` bleiben sinnvoll |

**Fazit:** PM kann parallel über Option A/B/C/D entscheiden. Engineering kann **M3 starten**, sobald PM die **Slugs** bestätigt hat (oder vorläufig mit Vorschlags-Slugs seeden).

---

## 7. Konkrete Empfehlung an den PM

1. **Slugs + Anzeigenamen** in §1 bestätigen (insb. KKRR).
2. **Kurzfristig Option A** freigeben — vier Kunden per Seed, Demo-Kunden für Tests behalten.
3. **Mittelfristig Option D:** Admin-API oder Admin-UI als **Phase-4-Epic** planen (`12`), inkl. Rolle `admin`, Audit, Soft-Delete.
4. **Nicht** Admin in M3–M7 mischen — verzögert Abnahme-Gates und erhöht Isolation-Risiko.

---

## 8. Offene PM-Fragen (Entscheidungsliste)

| # | Frage | Optionen |
|---|---|---|
| E1 | Finale Slugs für die 4 Kunden? | Tabelle §1 |
| E2 | Demo-Kunden `acme`/`globex` in Produktion behalten? | ja (nur Test-User) / nein |
| E3 | Wer darf Kunden sehen — 1 Nutzer alle 4 vs. getrennte Nutzer pro Kunde? | Zuordnungsmatrix |
| E4 | Kurzfristig Script-only (A) oder Admin-API (B) vor Live? | A empfohlen |
| E5 | Kunde löschen: Soft vs. Hard? Aufbewahrung? | Compliance |
| E6 | Wann Admin-UI (C)? | nach MVP / Phase 4 |

---

## 9. Nächste Schritte (nach PM-Rückmeldung)

| Wer | Aktion |
|---|---|
| **PM** | E1–E6 beantworten |
| **Engineering** | Seed mit 4 Kunden (+ Zuordnungen) anlegen |
| **Engineering** | M3 starten (Ingestion) — **ohne** Admin-UI |
| **PM** | Epic „Kunden- & Nutzer-Administration“ für Phase 4 backloggen |

---

## 10. Referenzen

- `02_product_requirements.md` — FR-20..FR-25, Persona P3
- `04_data_model.md` — `customers`, `user_customers`, Collection `kb_{id}`
- `07_auth_and_security.md` — Seed-only MVP, kein RBAC
- `09_implementation_plan.md` — M2 Kunden-Fundament, M7 Abnahme
- `12_roadmap.md` — Phase 4 Admin-UI / SSO / Audit
