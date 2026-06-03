# 02 — Product Requirements (PRD)

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

Übersetzt die Vision (`01`) in konkrete, prüfbare Anforderungen. Neu im Scope: **Datei-Upload**
und **Kundentrennung**.

---

## 1. Personas

### P1 — Support-Mitarbeiter „Sven"
- **Kontext:** betreut einen oder mehrere Kunden, beantwortet wiederkehrende Fragen unter Zeitdruck.
- **Braucht:** schnelle, belegte Antwort — **nur** aus dem Wissen des aktuell gewählten Kunden.
- **Erfolg:** wählt Kunden, stellt Frage, bekommt Antwort + Quelle, kann sie verifizieren.

### P2 — Wissens-Pflegerin „Petra"
- **Kontext:** kuratiert Runbooks/FAQ **pro Kunde**, oft als PDF/Word/Markdown.
- **Braucht:** Wissen per **Text und Datei** einpflegen und sehen, was im Kunden-Bestand liegt.
- **Erfolg:** lädt eine Datei in die KB des richtigen Kunden, sieht das Dokument in der Liste.

### P3 — Betreiber/Admin „Achim"
- **Kontext:** stellt das Tool bereit, legt **Kunden** und **Nutzer** an und ordnet sie zu.
- **Braucht:** reproduzierbares Setup, Anlage per Script, keine offenen Türen, harte Trennung.
- **Erfolg:** `docker compose up`, Kunden+Nutzer+Zuordnungen geseedet, Zugang nur mit Login.

## 2. User Stories

| ID | Als… | möchte ich… | damit… |
|---|---|---|---|
| US-1 | Nutzer | mich mit E-Mail + Passwort anmelden | nur Befugte Zugriff haben |
| US-2 | Nutzer | mich abmelden können | meine Sitzung beende |
| US-3 | Pfleger | Text mit Titel in die KB des aktiven Kunden einfügen | Wissen durchsuchbar wird |
| US-4 | Pfleger | die Dokumentliste des aktiven Kunden sehen | ich den Bestand überblicke |
| US-5 | Pfleger | ein Dokument des aktiven Kunden löschen | veraltetes Wissen entfernt wird |
| US-6 | Nutzer | eine Frage in natürlicher Sprache stellen | ich eine Antwort bekomme |
| US-7 | Nutzer | zu jeder Antwort die Quellen sehen | ich die Aussage prüfen kann |
| US-8 | Nutzer | bei fehlendem Wissen ein ehrliches „nichts gefunden" sehen | ich nicht fehlgeleitet werde |
| US-9 | Nutzer | Lade- und Fehlerzustände sehen | ich den Systemstatus verstehe |
| US-10 | Nutzer | (bei mehreren Berechtigungen) einen **Kunden auswählen** | ich im richtigen Kontext arbeite |
| US-11 | Pfleger | eine **Datei hochladen** (`.txt/.md/.pdf/.docx`) | Datei-Wissen in die KB kommt |
| US-12 | Nutzer | **nur** Dokumente des aktiven Kunden sehen/löschen | keine Vermischung passiert |
| US-13 | Nutzer | dass der Chat sich **nur** auf die KB des aktiven Kunden bezieht | keine Kunden-Leaks entstehen |

## 3. Funktionale Anforderungen

### Authentifizierung & Mandanten-Kontext
- **FR-1** Login-Seite (E-Mail + Passwort).
- **FR-2** Passwörter ausschließlich als **Argon2id**-Hash.
- **FR-3** Sitzung über signiertes Cookie; enthält `user_id` und `customer_id` (aktiver Kunde).
- **FR-4** Alle Inhalts-/API-Routen (außer Login/Health/Static) erfordern gültige Sitzung.
- **FR-5** Logout beendet die Sitzung.
- **FR-6** Nutzer werden per Seed-Script angelegt (kein Self-Signup).
- **FR-20** Es existiert eine **`customers`-Registry** (Seed) und `GET /api/customers` liefert die
  für den Nutzer erlaubten Kunden.
- **FR-21** **Nutzer↔Kunde-Zuordnung** als n:m (`user_customers`); ein Nutzer kann mehrere Kunden haben.
- **FR-22** Der **aktive Kunde** kommt **serverseitig aus der Session**. Bei genau einem erlaubten
  Kunden wird er beim Login automatisch gesetzt; bei mehreren wählt der Nutzer (`POST /api/session/customer`).
- **FR-25** Jeder Zugriff auf einen Kunden, für den der Nutzer **nicht** berechtigt ist → **403**.

### Wissensdatenbank / Ingestion (pro Kunde)
- **FR-7** Angemeldete Nutzer pflegen **Text** mit Titel in die KB des **aktiven Kunden** ein.
- **FR-23** Angemeldete Nutzer laden **Dateien** (`.txt/.md/.pdf/.docx/.png/.jpg/.jpeg/.webp/.gif`, max **30 MB**) per
  Multipart in die KB des aktiven Kunden hoch (`POST /api/documents`). Einfügen per **Drag&Drop, Klick oder Strg+V** (Screenshots als `.png`).
- **FR-23a** Vor Upload können PDF/DOCX/Bilddateien per `POST …/inspect` auf eingebettete Bilder geprüft werden; UI zeigt Thumbnails und erlaubt **selektive Vision-OCR**.
- **FR-8** Eingepflegtes Wissen (Text **oder** Datei) wird normalisiert, gechunkt, eingebettet und
  in die **kundenspezifische** Qdrant-Collection `kb_{customer_id}` geschrieben; Metadaten in
  SQLite mit `customer_id`.
- **FR-9** Leerer/zu kurzer Text wird mit klarer Fehlermeldung abgewiesen.
- **FR-24** Nicht unterstützter Dateityp → **400**; fehlgeschlagene Extraktion (leeres/kaputtes
  PDF/DOCX) → Dokument `status=failed`, **nichts** in Qdrant, klare UI-Meldung (**422**).
- **FR-10** Nutzer sehen die Dokumentliste **des aktiven Kunden** (Titel, Chunks, Quelle/Typ, Datum).
- **FR-11** Nutzer löschen ein Dokument des aktiven Kunden: Qdrant-Points entfernt **und**
  `deleted_at` gesetzt; danach unsichtbar in Liste/Suche.

### Agent / Chat (pro Kunde)
- **FR-12** Nutzer stellen Fragen über `POST /api/chat`.
- **FR-13** Antwort über Agent-Loop mit Tool `search_knowledge_base`, das **nur** die Collection
  des aktiven Kunden durchsucht.
- **FR-14** Tool 0..n-mal aufrufbar, begrenzt durch `MAX_TOOL_ROUNDS`.
- **FR-15** Citations **deterministisch aus Retrieval**, nicht aus freiem Modelltext.
- **FR-16** Keine Treffer über `MIN_SCORE_DEFAULT` → definierter „kein Wissen gefunden"-Text, keine
  erfundenen Quellen.
- **FR-17** Antwort mit Quellenliste (Dokumenttitel + Chunk-Index).

### System
- **FR-18** `GET /api/health` → `{"ok": true}` ohne Authentifizierung.
- **FR-19** Beim Start: SQLite-Tabellen sicherstellen; Kunden-Collections **lazy** bei erster
  Ingestion (oder für bekannte Kunden vorab) anlegen.

## 4. Nicht-funktionale Anforderungen

- **NFR-1 (Sicherheit)** Keine Klartext-Passwörter; Cookie `httponly`+`samesite=lax`; `.env` nicht
  im Repo; Fehlermeldungen ohne Secrets/Stacktraces.
- **NFR-2 (Reproduzierbarkeit)** Start aus sauberem Checkout via `docker compose up --build` (Ubuntu).
- **NFR-3 (Testbarkeit)** Unit-Tests ohne echte OpenAI-/Qdrant-Calls (gemockt); deterministisch.
- **NFR-4 (Konfigurierbarkeit)** Modelle, Schwellen, Top-K, Tool-Runden, Upload-Limit, erlaubte
  Extensions über `.env` steuerbar.
- **NFR-5 (Performance, Demo)** Chat-Antwort i. d. R. < 10 s bei kleiner KB; Upload bis 30 MB synchron.
- **NFR-6 (Wartbarkeit)** Klare Modulgrenzen (Auth / Tenant / Ingestion / Loader / Retrieval / Agent).
- **NFR-7 (Erweiterbarkeit)** **Ein** Ingestion-Kern `ingest_text(customer_id, ...)`; Loader nur
  davor; Schema mit `source_type/source_url/external_id` für spätere Quellen (Jira); Collection-Name
  aus `customer_id` abgeleitet.
- **NFR-8 (Sprache)** UI und Antworten auf Deutsch.
- **NFR-9 (Isolation)** **Tenant-Isolation ist Invariant:** jede Ingestion/Suche/Chat/Delete prüft
  serverseitig `user ∈ customer` und berührt nur `kb_{customer_id}`.
- **NFR-10 (Beobachtbarkeit, minimal)** Logging von Ingestion-Größen, Trefferzahl, Tool-Runden,
  Extraktionsergebnis (kein PII/Secret-Leak).

## 5. Akzeptanzkriterien (Abnahme-Gates)

| Bezug | Kriterium |
|---|---|
| US-1/FR-1..4 | Falsche Credentials → Fehler; geschützte Route ohne Session → Redirect/401 |
| US-10/FR-20..22 | Nutzer mit 1 Kunde → auto-aktiv; mit mehreren → Auswahl; aktiver Kunde aus Session |
| US-11/FR-23/FR-24 | **Gate 1:** PDF-Upload (Kunde 1) → Frage → Antwort **mit Quelle aus dem Dokument** |
| US-13/FR-25/NFR-9 | **Gate 2:** Nutzer/Kunde 2 sieht **keine** Doks von Kunde 1; Chat findet nichts aus Kunde 1; fremder Kunde → 403 |
| FR-24 | **Gate 3:** kaputtes/leeres PDF → `status=failed`, klare Meldung, **nichts** in Qdrant |
| US-8/FR-16 | Frage ohne Wissen → definierter „nichts gefunden"-Text, keine Quellen |
| NFR-3 | `pytest` grün ohne Netzzugriff; Isolation-Tests Pflicht |

Detaillierte Testfälle: `10_testing_strategy.md`.

## 6. Außerhalb des Scopes
Siehe `01` §5 und `12_roadmap.md` (Jira, SSO, Admin-UI, Versionierung, Chat-Dateianhang).
