# `backend/app/tests/test_agent.py`

**Quellpfad:** `backend/app/tests/test_agent.py`

## Zweck und logischer Aufbau

End-to-End-Tests für den **Chat-Agenten** über `POST /api/chat`: Tool-Aufruf `search_knowledge_base`, Verhalten bei leeren Treffern (`NO_CONTEXT_TEXT`), Quellenliste bei Hits, Filterung nur zitierter Quellen (`[n]` in der Antwort), sowie Randfälle (fehlender aktiver Mandant, leere Nachricht).

Die Datei definiert ein lokales Test-Double `FakeLLM` und steuert das LLM über `set_llm` aus `app.llm`. Retrieval wird per `monkeypatch` auf `app.agent.search_knowledge_base_scoped` ersetzt.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.agent.run` (indirekt via Route)
  - `app.llm.LLMResponse`, `ToolCall`, `set_llm`
  - `app.prompts.NO_CONTEXT_TEXT`
  - `app.retrieval.RetrievalHit`
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
  - `dataclasses.dataclass`, `pytest`, `monkeypatch`
- **Wird genutzt von:** pytest
- **HTTP / UI:** `POST /api/chat`, `POST /api/session/customer`, `POST /login`
- **Daten:** SQLite-Mandanten/User; keine echten Qdrant/OpenAI-Aufrufe (Conftest-Mocks + FakeLLM)
- **Abgedecktes Modul:** `backend/app/agent.py`, `backend/app/routes.py` (Chat-Route)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `FakeLLM` | `@dataclass` | Test-Double für LLM mit vordefinierter Antwortsequenz `scripted` |

## Funktionen und Klassen

### `FakeLLM`

**Beschreibung:** Simuliert LLM-`chat`-Aufrufe durch Abarbeiten einer `list[LLMResponse]`.

**Klassenattribute:**

| Feld | Typ | Beschreibung |
|---|---|---|
| `scripted` | `list[LLMResponse]` | Queue; wird von `chat` mit `pop(0)` verbraucht |

### `FakeLLM.chat(messages, tools=None) -> LLMResponse`

**Beschreibung:** Liefert nächste skriptierte Antwort oder wirft `AssertionError`, wenn die Queue leer ist.

**Parameter / Rückgabe:** `messages`, `tools` — wie Produktions-LLM; Rückgabe `LLMResponse`.

**Ablauf / lokale Variablen:** Prüft `self.scripted`; `pop(0)`.

**Aufrufer / Aufgerufene:** Wird von `app.agent` / LLM-Abstraktion aufgerufen, wenn `set_llm(llm)` gesetzt ist.

---

### `test_agent_no_context_without_hits(client, db_session, monkeypatch)`

**Beschreibung:** Leere Retrieval-Ergebnisse → `no_context: true`, Antwort `NO_CONTEXT_TEXT`, leere `sources`.

**Parameter / Rückgabe:** `client`, `db_session`, `monkeypatch`.

**Ablauf / lokale Variablen:** `FakeLLM` mit Tool-Call dann Textantwort; `fake_search` liefert `[]`; `payload` aus JSON; `set_llm(None)` im Cleanup.

**Aufrufer / Aufgerufene:** `monkeypatch.setattr("app.agent.search_knowledge_base_scoped", fake_search)`; `POST /api/chat`.

---

### `test_agent_returns_sources_when_hits(client, db_session, monkeypatch)`

**Beschreibung:** Ein Treffer → eine Quelle, Antwort enthält Inhalt aus LLM.

**Ablauf / lokale Variablen:** `hit` — `RetrievalHit` für „VPN Runbook“; Lambda-Retrieval gibt `[hit]`; `payload["no_context"] is False`, `sources[0]["title"]`.

---

### `test_agent_only_returns_cited_sources(client, db_session, monkeypatch)`

**Beschreibung:** Drei Hits, LLM zitiert nur `[2]` → genau eine Quelle mit `n == 2`.

**Ablauf / lokale Variablen:** `hits` — drei `RetrievalHit`; Antwort „Mo–Fr 8–17 Uhr laut [2].“

---

### `test_chat_requires_customer(client, db_session)`

**Beschreibung:** Chat ohne gesetzten aktiven Mandanten → 403.

**Ablauf / lokale Variablen:** User mit zwei Mandanten, kein `POST /api/session/customer`.

**Aufrufer / Aufgerufene:** Tenant-Guard in `routes.py` / `tenant.py`.

---

### `test_chat_empty_message(client, db_session)`

**Beschreibung:** Nur Whitespace in `message` → 400, `error: "empty_message"`.

**Ablauf / lokale Variablen:** Aktiver Mandant gesetzt; `message: "   "`.

## (Optional) Tests

- **Fixtures:** `client`, `db_session`, `monkeypatch`; autouse `fake_embeddings`, `fake_vector_store`. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/agent.py`, `backend/app/routes.py`, `backend/app/llm.py`, `backend/app/retrieval.py`, `backend/app/prompts.py`.

| Test | Intent |
|---|---|
| `test_agent_no_context_without_hits` | Keine KB-Treffer → Standard-No-Context-Antwort |
| `test_agent_returns_sources_when_hits` | Treffer → Quellen in Response |
| `test_agent_only_returns_cited_sources` | Nur im Text zitierte `[n]`-Quellen |
| `test_chat_requires_customer` | 403 ohne aktiven Mandanten |
| `test_chat_empty_message` | 400 bei leerer Nachricht |
