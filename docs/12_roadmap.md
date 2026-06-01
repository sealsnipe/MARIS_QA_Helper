# 12 — Roadmap

**Stand:** 2026-06-02 · **Status:** Orientierung, nicht MVP-bindend

**Datei-Upload und Mandantentrennung sind bereits im MVP** (nicht mehr Roadmap). Die folgenden
Phasen sind additiv; vorbereitete Haken sind genannt.

---

## Phase 2 — Jira-Read-Connector
- `connectors/jira.py`: read-only JQL → je Issue normalisiertes Markdown (Key, Summary,
  Description, Status, Updated, URL, optional Kommentare).
- Indexierung über `ingest_text(customer_id, source_type="jira", external_id=ISSUE_KEY,
  source_url=.../browse/KEY)` — selber Kern wie Text/Datei.
- **Dedup:** gleiche `external_id` → alte Chunks ersetzen (Unique-Constraint
  `(customer_id, source_type, external_id)`).
- **Zwei Modi:** Import (Issues werden KB-Inhalt) oder Live-Tool `search_jira(jql)` als zusätzliches
  Agent-Tool.
- **Isolation (kritisch):** freies JQL pro Kunde gegen eine **Projekt-Allowlist** prüfen — sonst
  kann ein Kunden-Scope fremde Projekte importieren.
- **Sicherheit:** nur lesend, keine Schreiboperationen.
- **Vorhandene Haken (MVP):** `source_type/source_url/external_id`; generische Quellen-Labels;
  tool-agnostischer Agent-Loop; Mandanten-Scoping.

## Phase 3 — Erweiterte Ingestion
- Mehrfach-Datei-Upload, Drag&Drop mehrerer Dateien.
- Confluence-Sync; scheduled Re-Index; Background-Jobs für große Uploads (asynchrone Indexierung).
- Duplikaterkennung via `text_sha256`, Dokument-Versionierung.
- Tabellen-/Bildextraktion aus PDF/DOCX (über reine Absatztexte hinaus).

## Phase 4 — Auth & Compliance
- SSO (Entra/Okta) — `get_current_user`/`get_current_customer` bleiben, nur Login-Schritt tauscht.
- Rollen/Rechte **innerhalb** eines Kunden; Admin-UI für Kunden/Nutzer/Zuordnungen.
- Audit-Log (User + Customer + Aktion); CSRF-Token für Formulare/Upload; Login-Throttling.
- Secrets-Manager statt `.env`, Key-Rotation; DSGVO/AVV-Review; EU-/Azure-Hosting; PII-Redaction;
  Verschlüsselung at rest.

## Phase 5 — Bessere Retrieval-Qualität
- Hybrid-Suche (Keyword + Vektor), Reranker.
- Chunk-Vorschau/-Qualitätsanzeige im UI; Eval-Fragenset & Dashboard.
- Wechsel auf lokale/EU-Embeddings (`bge-m3`, `multilingual-e5-large`) — dann query/passage-Prefixe
  + Collection-Neuanlage beachten.

## Phase 6 — Agenten-Workflows (mit Seiteneffekten)
- Aktionen statt nur Antworten: Jira-Ticket aus Antwort, Antwort-Entwurf, Eskalation an Mensch,
  kundenspezifische Runbook-Checklisten. Erfordert Human-in-the-loop-Bestätigungen.

## Phase 7 — Orchestrierung & Betrieb
- Optionaler n8n-Layer (Chat-Trigger/Sync) ruft die bestehende API — **nicht** RAG-Logik in n8n.
- Monitoring/Tracing, Metriken, Alerting.

---

### Leitplanken (gelten dauerhaft)
- **Kundentrennung ist ab MVP Invariant:** jede Ingestion/Suche/Chat/Delete verlangt den aktiven
  `customer_id` (aus der Session) und berührt nur `kb_{customer_id}`; `user ∈ customer` wird
  serverseitig geprüft.
- RAG-Kern bleibt in der getesteten API, nicht in Workflow-Tools.
- Neue Quellen docken über `ingest_text(customer_id, ...)` an; neue Fähigkeiten über zusätzliche
  Agent-Tools.
