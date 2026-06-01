# 01 — Vision & Scope

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

---

## 1. Problem

Support-Wissen (Runbooks, Eskalationswege, FAQ, Lösungsschritte) liegt verstreut — und in
**Dateien** (PDF, Word, Markdown), nicht als kopierbarer Fließtext. Außerdem arbeiten Support-
Teams **für mehrere Kunden**: Wissen und Antworten von Kunde A dürfen nie bei Kunde B landen.
Es fehlt ein zentraler Ort, an dem man Wissen realistisch einpflegt und eine **belegte,
kundengetrennte** Antwort in natürlicher Sprache bekommt.

## 2. Vision

Ein leichtgewichtiges, selbst gehostetes Werkzeug, in dem das Team:

1. sich anmeldet und (bei mehreren Berechtigungen) einen **Kunden** wählt,
2. Wissen **per Text und per Datei** in die **isolierte** KB dieses Kunden einpflegt,
3. Fragen stellt und vom Agenten eine Antwort **mit Quellen** erhält — **nur** aus der KB des
   aktiven Kunden.

Der Agent entscheidet selbst, ob/wie oft er die Kunden-KB durchsucht, bevor er antwortet. Das
schafft die Grundlage, später weitere Werkzeuge (z. B. Jira-Suche) anzudocken.

**Kern-These (MVP):** Agentengestütztes RAG mit belegten Antworten, **pro Kunde isoliert**,
Wissen per **Text und Datei** über die UI — hinter Login. Das beweist einen **realistischen
Support-Workflow**, nicht nur eine abstrakte RAG-Demo.

## 3. Zielgruppe

- **Primär:** Support-/IT-Mitarbeitende, die für einen oder mehrere Kunden belegte Antworten brauchen.
- **Sekundär:** Wissens-Pflegende, die Inhalte (auch als Datei) aktuell halten.
- **Betrieb:** kleine interne Gruppe; Login + Kunden-Zuordnung pro Nutzer.

Personas: `02_product_requirements.md`.

## 4. Ziele (MVP)

- **G1** — Angemeldete Nutzer pflegen Wissen **per Text und per Datei** (`.txt/.md/.pdf/.docx`).
- **G2** — Antworten beruhen **nur** auf der KB des **aktiven Kunden**.
- **G3** — Jede Antwort zeigt nachvollziehbare Quellen (Dokumenttitel + Chunk).
- **G4** — Ohne belastbaren Treffer sagt der Agent das offen statt zu halluzinieren.
- **G5** — Zugang ist durch Login geschützt; Nutzer sind unterscheidbar.
- **G6** — `docker compose up --build` startet das System reproduzierbar.
- **G7** — **Kundentrennung:** Kunde A sieht nie Dokumente oder Antworten von Kunde B.

## 5. Nicht-Ziele (bewusst NICHT im MVP)

- ❌ Jira-/Confluence-Anbindung (nur als Erweiterungspfad vorbereitet)
- ❌ SSO / Rollen- & Rechteverwaltung (nur einfaches Login + Kunden-Zuordnung)
- ❌ Admin-UI für Kunden/Nutzer (Anlage per Seed-Script)
- ❌ Self-Service-Registrierung
- ❌ Chat-Dateianhang („Datei nur für diese eine Frage") — Upload = **KB-Ingestion**
- ❌ Agenten-Aktionen mit Seiteneffekten (Tickets anlegen, Mails senden)
- ❌ Produktive DSGVO-Workflows, Audit-Logs, Verschlüsselung at rest, Secrets-Manager
- ❌ Dokument-Versionierung, Duplikaterkennung, Re-Index-Scheduling, Hintergrund-Jobs, Eval-Dashboards

> **Scope-Hinweis:** Datei-Upload und Mandantentrennung waren in einer früheren Planversion
> „später" — sie sind jetzt **bewusst Teil des MVP**, weil ohne sie der echte Support-Workflow
> nicht testbar ist und nachträgliches Nachrüsten der Isolation teurer wäre.

## 6. Erfolgskriterien

Der MVP gilt als erfolgreich, wenn (Abnahme-Gates, vgl. `10`):

1. **Upload:** Angemeldeter Nutzer / Kunde 1 lädt ein PDF hoch → Frage → korrekte Antwort **mit
   Quelle aus diesem Dokument**.
2. **Isolation:** Nutzer / Kunde 2 sieht **keine** Dokumente von Kunde 1; Chat findet **nichts**
   aus Kunde 1.
3. **Robuste Extraktion:** kaputtes/leeres PDF → Dokument `status=failed`, klare UI-Meldung,
   **nichts** in Qdrant.
4. Frage ohne passendes Wissen → ehrliches „nicht in der Wissensdatenbank gefunden".
5. Geschützte Routen ohne Session → Login-Redirect/401; Zugriff auf fremden Kunden → 403.
6. `docker compose up --build` aus sauberem Checkout; Tests grün ohne echte API-Calls.

## 7. Annahmen & Abhängigkeiten

- Gültiger **OpenAI API-Key** in `.env`.
- **Entwicklung in WSL2/Ubuntu**, **Deployment auf Ubuntu** (Docker/Compose vorhanden).
- Initiale Kunden, Nutzer (+ Zuordnungen) und Demo-Inhalte werden per Seed-Script eingespielt.
- Netzwerkzugang zu `api.openai.com`.

## 8. Risiken (MVP-relevant)

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| **Cross-Tenant-Leak** | schwerwiegend | zentrale `get_current_customer`-Dependency; `customer_id` nur aus Session; getrennte Collections; **Pflicht-Isolation-Tests** |
| Kaputte/leere PDF-/DOCX-Extraktion | unbrauchbare KB, Frust | `status=failed`, klare Meldung, nichts indexieren |
| Schlechte Retrieval-Qualität | Antworten unbrauchbar | `min_score`/`top_k` als Env, empirisch tunen; Quellen sichtbar |
| Modell halluziniert trotz RAG | Vertrauensverlust | strenger System-Prompt + Citations aus Retrieval |
| Große Dateien / langsame Ingestion | Timeouts | `MAX_UPLOAD_MB=30`, MVP synchron, sonst Roadmap-Background-Jobs |
| Dev/Prod-Drift (Windows→Ubuntu) | „lief lokal, crasht am Server" | Entwicklung in WSL2/Ubuntu, `.gitattributes` (LF), Case-Disziplin |
| Geheimnis-Leak (`.env`, Key) | Sicherheitsvorfall | `.env` gitignored, Fehler ohne Secrets |

## 9. Kernentscheidungen (Snapshot)
Siehe `README.md` → „Festgelegte Kernentscheidungen". Abweichungen werden als ADR in
`03_architecture.md` dokumentiert.
