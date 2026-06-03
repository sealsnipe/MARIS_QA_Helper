# `backend/app/agent.py`

**Quellpfad:** `backend/app/agent.py`

## Zweck und logischer Aufbau

Kernmodul des RAG-Chat-Agenten: eine Nutzerfrage wird mit optionalem Mandanten-System-Prompt an das LLM geschickt; das Modell darf das Tool `search_knowledge_base` aufrufen, um Wissensbasis-Treffer zu holen. Treffer werden in einer `SourceRegistry` gesammelt, dem Modell als Tool-Antworten zurückgegeben und schließlich als zitierte Quellen gefiltert.

Lesereihenfolge: Imports → `AgentError` / `ChatResult` → `run()` (Hauptschleife mit `MAX_TOOL_ROUNDS`, Tool-Handling, Fallback ohne Tools). Im Request-Flow ruft `routes.py` nach Speichern der User-Nachricht `run()` auf und persistiert das Ergebnis via `chats.add_message`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.config.get_settings` — Top-K, Tool-Runden
  - `app.llm.LLMBackend`, `LLMError`, `get_llm` — Chat-Completion mit Tools
  - `app.prompts.DEFAULT_GLOBAL_SYSTEM_PROMPT`, `NO_CONTEXT_TEXT`, `SEARCH_TOOL`
  - `app.retrieval` — Suche, Quellenformatierung, Zitationsfilter
  - `app.system_prompts.get_effective_system_prompt` — mandantenspezifischer Prompt
  - `sqlalchemy.orm.Session`
- **Wird genutzt von:**
  - `backend/app/routes.py` — `run as run_agent` im Chat-Endpoint
  - `backend/app/main.py` — `AgentError`-Exception-Handler
  - `backend/app/tests/test_agent.py`, `test_tenant_isolation.py`
  - `backend/app/tests/test_chats.py` — `ChatResult`-Typ
- **HTTP / UI:** indirekt über Chat-POST in `routes.py` (kein eigener Router)
- **Daten:** Qdrant via `search_knowledge_base_scoped`; optional SQLite für System-Prompt

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `AgentError` | Exception-Klasse | Agent-Fehler mit maschinenlesbarem `code` und optionalem `detail` |
| `ChatResult` | Dataclass | Ergebnis: `answer`, `sources`, `no_context` |

## Funktionen und Klassen

### `AgentError`

**Beschreibung:** Signalisiert Agent-Laufzeitfehler (z. B. LLM-Ausfall).

**Attribute:** `code: str`, `detail: str | None`.

**Aufrufer / Aufgerufene:** Wird in `run()` bei `LLMError` geworfen; fängt `main.py`.

---

### `ChatResult`

**Beschreibung:** Rückgabecontainer für eine Agent-Antwort.

| Feld | Typ | Beschreibung |
|---|---|---|
| `answer` | `str` | Antworttext (oder `NO_CONTEXT_TEXT`) |
| `sources` | `list[dict[str, Any]]` | Gefilterte Quellen mit Metadaten |
| `no_context` | `bool` | `True`, wenn keine verwertbaren KB-Treffer |

**Aufrufer / Aufgerufene:** Von `run()` erzeugt; von `routes.py` und Tests konsumiert.

---

### `run(customer_id, message, top_k=None, *, db=None, llm=None, system_prompt=None, scope_customer_ids=None) -> ChatResult`

**Beschreibung:** Führt eine einzelne Agent-Runde (evtl. mehrere Tool-Iterationen) für eine Nutzerfrage aus.

**Parameter / Rückgabe:**
- `customer_id` — Mandanten-Slug für Retrieval
- `message` — Nutzerfrage (wird getrimmt)
- `top_k` — optionales Retrieval-Limit (geclampt via `clamp_top_k`)
- `db` — optional für effektiven System-Prompt aus DB
- `llm` — injizierbares LLM-Backend (Default: `get_llm()`)
- `system_prompt` — Override; sonst DB oder `DEFAULT_GLOBAL_SYSTEM_PROMPT`
- `scope_customer_ids` — optionale Mandantenliste für scoped Search
- **Rückgabe:** `ChatResult`

**Ablauf / lokale Variablen:**
- `settings`, `default_top_k` — Konfiguration und geklemmtes Top-K
- `messages` — Chat-Verlauf (system, user, assistant, tool)
- `registry` — `SourceRegistry` für alle KB-Treffer
- `source_offset` — fortlaufende Quellennummerierung für das Modell
- Schleife bis `MAX_TOOL_ROUNDS`: LLM-Call mit `SEARCH_TOOL`; bei Tool-Calls Treffer suchen, registrieren, als Tool-Content anhängen
- Ohne Tool-Calls: bei fehlenden Treffern oder leerer Antwort → `NO_CONTEXT_TEXT`; sonst Zitationsfilter auf Quellen
- Nach Schleifenende: finaler LLM-Call ohne Tools, gleiche No-Context-/Quellenlogik

**Aufrufer / Aufgerufene:**
- Ruft auf: `get_settings`, `get_llm`, `clamp_top_k`, `get_effective_system_prompt`, `llm.chat`, `search_knowledge_base_scoped`, `SourceRegistry.register`, `format_hits_for_model`, `filter_sources_by_answer_citations`
- Aufrufer: `routes.py` (`run_agent`), Tests
