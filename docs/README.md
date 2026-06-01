# SUP_QA_Helper — Planungsdokumentation

**Projekt:** SUP_QA_Helper (Support Q&A Helper)
**Status:** Planung / Pre-Implementation
**Stand:** 2026-06-02
**Verantwortlich:** Product Owner + Projektleitung + Engineering (eine Rolle, Claude)

---

## Worum geht es?

Ein selbst gehostetes, agentengestütztes RAG-Tool für den Support: Nutzer melden sich an,
wählen (bei mehreren Berechtigungen) einen **Kunden**, befüllen dessen **isolierte**
Wissensdatenbank per **Text und Datei-Upload** und stellen Fragen an einen **fähigen Agenten**,
der nur diese Kunden-KB durchsucht und mit **Quellenangaben** antwortet.

Kern-These des MVP: *Agentengestütztes RAG mit belegten Antworten, **pro Kunde isoliert**,
Wissen per **Text und Datei** über die UI — hinter Login.*

Integrationen (Jira) und SSO bleiben Roadmap; **Datei-Upload und Kundentrennung sind Teil
dieses Prototyps**.

## Wie diese Doku zu lesen ist

Empfohlene Reihenfolge: **01 → 02 → 03**, danach themenspezifisch.

| # | Dokument | Zweck | Zielgruppe |
|---|---|---|---|
| — | `README.md` (dieses) | Einstieg, Index, Konventionen | alle |
| 01 | `01_vision_and_scope.md` | Warum, Ziel, Scope in/out, Erfolgskriterien | PO, Stakeholder |
| 02 | `02_product_requirements.md` | Personas, User Stories, FR/NFR, Akzeptanz | PO, Engineering, QA |
| 03 | `03_architecture.md` | Systemaufbau, Stack, Datenflüsse, Entscheidungen | Engineering |
| 04 | `04_data_model.md` | SQLite- und Qdrant-Schema (inkl. Mandanten) | Engineering |
| 05 | `05_api_specification.md` | Endpoints, Requests/Responses, Fehler | Engineering, QA |
| 06 | `06_agent_and_rag_design.md` | Agent-Loop, Tools, Prompts, Retrieval, Citations | Engineering |
| 07 | `07_auth_and_security.md` | Login, Hashing, Sessions, Mandanten-Checks, Upload | Engineering |
| 08 | `08_ui_ux_design.md` | Seiten, Wireframes, Kundenauswahl, Upload, Zustände | Engineering, Design |
| 09 | `09_implementation_plan.md` | Tasks, Build-Reihenfolge (M1–M7), Meilensteine, DoD | Engineering, PM |
| 10 | `10_testing_strategy.md` | Testebenen, Mocking, Isolation-Tests, Smoke | QA, Engineering |
| 11 | `11_setup_and_operations.md` | Env, Docker, WSL2-Dev, Ubuntu-Deploy, Seed, Betrieb | Engineering, Ops |
| 12 | `12_roadmap.md` | Spätere Phasen: Jira, SSO, Admin-UI | PO, Engineering |
| 13 | `13_coding_agent_brief.md` | Verbindliche Bau-Anweisung (M1–M7, Invarianten, Git, Setup) | Coding-Agent |

> **`13_coding_agent_brief.md`** ist die Einstiegs- und Bau-Anweisung für den bauenden
> Coding-Agent und referenziert die übrigen Dokumente als Quelle der Wahrheit.

## Festgelegte Kernentscheidungen (Snapshot)

- **Backend/UI:** Python 3.12, FastAPI + Jinja2, server-gerendert + minimales Vanilla-JS
- **Vektor-DB:** Qdrant — **eine Collection pro Kunde** (`kb_{customer_id}`)
- **Metadaten-DB:** SQLite (`users`, `customers`, `user_customers`, `documents`, `chunks`)
- **Mandanten:** Kundentrennung ist **MVP-Invariant** — jede Ingestion/Suche/Chat/Delete ist
  auf den aktiven Kunden gescoped; aktiver Kunde lebt **serverseitig in der Session**
- **Wissensaufnahme:** **Text-Eingabe und Datei-Upload** (`.txt`, `.md`, `.pdf`, `.docx`,
  max **30 MB**) — beide über den gemeinsamen `ingest_text()`-Kern
- **Modelle:** OpenAI `text-embedding-3-small` (1536 dim) + `gpt-4.1-mini` (Chat)
- **Modell-Auth:** OpenAI **API-Key** aus `.env` (kein OAuth)
- **Agent:** hand-gerollter Tool-Calling-Loop, Tool `search_knowledge_base` (an aktiven Kunden gebunden)
- **Login:** SQLite-`users`, **Argon2id**-Hash, signiertes Session-Cookie, kein Self-Signup
- **Sprache UI/Antworten:** Deutsch
- **Port:** 8088
- **Entwicklung:** in **WSL2/Ubuntu** (Dev-Prod-Parität); **Deployment auf Ubuntu** via Docker Compose

## Konventionen

- **Sprache:** Fließtext deutsch; Code/Bezeichner/Schemata/Prompts englisch (außer der
  deutschsprachige System-Prompt für Antworten).
- **IDs:** `FR-x`, `NFR-x`, `US-x`, `T-x`, `ADR-x`.
- **Mandanten-Kontext:** `customer_id` ist Pflicht-Kontext für alle Wissens-/Chat-Operationen
  und wird **immer serverseitig aus der Session** bezogen, nie vom Client übernommen.

## Glossar

| Begriff | Bedeutung |
|---|---|
| **Kunde / Customer / Mandant** | Synonyme: eine isolierte Wissens-/Chat-Einheit. Ein Kunde = eine Qdrant-Collection `kb_{customer_id}` + eigene `documents`-Zeilen. |
| **customer_id** | Slug-Identifier eines Kunden (z. B. `acme`), Teil des Collection-Namens |
| **aktiver Kunde** | Der in der Session gewählte Kunde, gegen den alle Operationen laufen |
| **KB** | Knowledge Base / Wissensdatenbank — **pro Kunde** eine |
| **RAG** | Retrieval-Augmented Generation |
| **Chunk** | Eingebetteter, durchsuchbarer Textabschnitt eines Dokuments |
| **Loader** | Komponente, die aus einer Datei (txt/md/pdf/docx) Text extrahiert |
| **Citation/Quelle** | Verweis auf Quelldokument + Chunk der Antwort |
| **Ingestion** | Aufnahme von Text in die KB (chunk → embed → speichern) |
| **Tenant-Isolation** | Garantie, dass Kunde A nie Daten/Antworten von Kunde B sieht |
