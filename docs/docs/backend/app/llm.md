# `backend/app/llm.py`

**Quellpfad:** `backend/app/llm.py`

## Zweck und logischer Aufbau

Abstraktionsschicht für **Chat-LLM-Aufrufe** mit optionaler Tool-Unterstützung. Das Modul kapselt zwei Backends: OpenAI-kompatibles Chat Completions (`OpenAILLM`) und Codex-OAuth-Streaming (`CodexOAuthLLM`).

Lesereihenfolge: Dataclasses (`ToolCall`, `LLMResponse`) und `LLMBackend` (Protocol) → Hilfsfunktion `_last_user_message` → Backend-Klassen → Singleton `get_llm` / `set_llm`.

Im Agent-Datenfluss (`app.agent.run_chat`) wird `get_llm().chat(messages, tools=[SEARCH_TOOL])` aufgerufen. `CodexOAuthLLM` synthetisiert bei Tool-Anfrage ohne vorherige Tool-Ergebnisse einen initialen `search_knowledge_base`-Tool-Call, damit die RAG-Pipeline auch ohne natives Function-Calling des Codex-Backends funktioniert.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.config.get_settings`, `openai.OpenAI`, `httpx`, `oauth_codex` (lazy in `CodexOAuthLLM._headers`), `json`, `uuid`, `pathlib.Path`
- **Wird genutzt von:** `backend/app/agent.py` (`LLMBackend`, `LLMError`, `get_llm`), Tests in `test_agent.py`, `test_tenant_isolation.py` (`set_llm`, `LLMResponse`, `ToolCall`)
- **HTTP / UI / CLI:** indirekt über Chat-API in `routes.py`; Codex-Backend POST auf `{CODEX_BASE_URL}/responses` (SSE)
- **Daten:** keine persistenten Stores in diesem Modul

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `LLMError` | Exception-Klasse | Allgemeiner LLM-Fehler (API, OAuth, leere Antwort) |
| `ToolCall` | Dataclass | Normalisierter Tool-Aufruf (`id`, `name`, `arguments`) |
| `LLMResponse` | Dataclass | Chat-Antwort inkl. `assistant_message` für Message-History |
| `LLMBackend` | Protocol | Vertrag: `chat(messages, tools?) -> LLMResponse` |
| `_llm_backend` | Modul-Variable | Singleton-Cache (`LLMBackend \| None`) |

## Funktionen und Klassen

### `LLMError`

**Beschreibung:** Basis-Exception für alle LLM-Backend-Fehler; Message enthält Fehlertext oder Code (z. B. `oauth_codex_missing`, `empty_answer`).

---

### `ToolCall` (Dataclass)

| Feld | Typ | Beschreibung |
|---|---|---|
| `id` | `str` | Tool-Call-ID (API oder synthetisch) |
| `name` | `str` | Funktionsname (z. B. `search_knowledge_base`) |
| `arguments` | `dict[str, Any]` | Parsed JSON-Argumente |

---

### `LLMResponse` (Dataclass)

| Feld | Typ | Beschreibung |
|---|---|---|
| `content` | `str \| None` | Assistant-Text (kann `None` bei reinem Tool-Call sein) |
| `tool_calls` | `list[ToolCall]` | Liste erkannter oder synthetisierter Tool-Aufrufe |
| `assistant_message` | `dict[str, Any]` | OpenAI-kompatibles Message-Dict für Conversation-History |

---

### `_last_user_message(messages: list[dict[str, Any]]) -> str`

**Beschreibung:** Extrahiert den Inhalt der letzten User-Nachricht aus der Message-Liste.

**Parameter / Rückgabe:** `messages` — Chat-History; Rückgabe String-Inhalt oder `""` wenn keine User-Message.

**Ablauf / lokale Variablen:** Iteriert `reversed(messages)`, prüft `role == "user"` und `isinstance(content, str)`.

**Aufrufer / Aufgerufene:** Aufgerufen von `CodexOAuthLLM.chat` für synthetischen Tool-Call.

---

### `OpenAILLM`

**Beschreibung:** Standard-Backend über OpenAI Chat Completions API mit nativer Tool-Call-Unterstützung.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `_client` | `OpenAI` | HTTP-Client |
| `_model` | `str` | Chat-Modellname |

---

### `OpenAILLM.__init__(api_key: str, base_url: str, model: str) -> None`

**Beschreibung:** Initialisiert Client und Modellname.

**Aufrufer / Aufgerufene:** Instanziiert von `get_llm()` wenn `uses_chatgpt_oauth` falsch.

---

### `OpenAILLM.chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse`

**Beschreibung:** Ruft Chat Completions auf, parst Tool-Calls und baut `assistant_message`.

**Parameter / Rückgabe:** `messages` — OpenAI-Message-Liste; `tools` — optional Tool-Schema; bei gesetzten Tools auch `tool_choice="auto"`.

**Ablauf / lokale Variablen:** `kwargs` — Request-Parameter; `response` — API-Antwort; `choice` — erste Message; `tool_calls` — geparste `ToolCall`-Liste (JSON-Fehler → leeres `{}`); `assistant_message` — rekonstruierte Assistant-Message inkl. serialisierter Tool-Calls.

**Aufrufer / Aufgerufene:** Aufgerufen von `agent.run_chat`; wirft `LLMError` bei API-Exceptions.

---

### `CodexOAuthLLM`

**Beschreibung:** Codex-Streaming-Backend; synthetisiert initialen Tool-Call wenn Tools angefordert und noch keine Tool-Ergebnisse in der History sind.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `_auth_path` | `Path` | Pfad zum OAuth-Token-Store |
| `_base_url` | `str` | Codex-API-Basis-URL (ohne trailing slash) |
| `_model` | `str` | Modellname für `/responses` |

---

### `CodexOAuthLLM.__init__(auth_path: Path, base_url: str, model: str) -> None`

**Beschreibung:** Speichert Auth-Pfad, normalisierte Base-URL und Modell.

**Aufrufer / Aufgerufene:** Instanziiert von `get_llm()` wenn `settings.uses_chatgpt_oauth` wahr.

---

### `CodexOAuthLLM._headers() -> dict[str, str]`

**Beschreibung:** Baut authentifizierte HTTP-Header für Codex SSE-Requests.

**Parameter / Rückgabe:** Rückgabe Dict mit Auth-, `Content-Type: application/json`, `Accept: text/event-stream`.

**Ablauf / lokale Variablen:** Lazy-Import `oauth_codex.Client`, `FileTokenStore`; `client` — authentifizierter OAuth-Client.

**Aufrufer / Aufgerufene:** Aufgerufen von `_stream_response`; wirft `LLMError("oauth_codex_missing")` bei ImportError.

---

### `CodexOAuthLLM.chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse`

**Beschreibung:** Entweder synthetischer `search_knowledge_base`-Tool-Call oder Streaming-Antwort über Codex `/responses`.

**Parameter / Rückgabe:** Wie `OpenAILLM.chat`.

**Ablauf / lokale Variablen:** `has_tool_results` — prüft ob `role=="tool"` in Messages; bei Tools ohne Tool-Ergebnisse: `query` aus `_last_user_message`, synthetischer `ToolCall` mit `call_{uuid}`; sonst: `system_parts`/`instructions`, gefilterte `input_messages` (User/Assistant + Tool-Ergebnisse als User-Prefix), `payload` mit `stream=True`, `answer` via `_stream_response`.

**Aufrufer / Aufgerufene:** Aufgerufen von `agent.run_chat`; ruft `_last_user_message`, `_stream_response`, `_headers`.

---

### `CodexOAuthLLM._stream_response(payload: dict[str, Any]) -> str`

**Beschreibung:** POST auf `{base_url}/responses`, parst SSE `data:`-Zeilen und sammelt Text-Deltas.

**Parameter / Rückgabe:** `payload` — Codex-Request-Body; Rückgabe zusammengefügter Antworttext.

**Ablauf / lokale Variablen:** `parts` — gesammelte Delta-Strings; bei HTTP ≥400: `body` gelesen, `LLMError` mit Status und gekürztem Body; parst Events mit `type == "response.output_text.delta"`.

**Aufrufer / Aufgerufene:** Aufgerufen von `chat`; wirft `LLMError("empty_answer")` wenn Ergebnis leer.

---

### `get_llm() -> LLMBackend`

**Beschreibung:** Lazy Singleton: wählt `CodexOAuthLLM` oder `OpenAILLM` anhand `settings.uses_chatgpt_oauth`.

**Parameter / Rückgabe:** Keine Parameter; Rückgabe `LLMBackend`.

**Ablauf / lokale Variablen:** `settings` — `get_settings()`; bei OAuth: `auth_path` aus `codex_oauth_auth_path`.

**Aufrufer / Aufgerufene:** Aufgerufen von `agent.run_chat`.

---

### `set_llm(backend: LLMBackend | None) -> None`

**Beschreibung:** Ersetzt den globalen LLM-Singleton (Tests).

**Parameter / Rückgabe:** `backend` — Mock oder `None`.

**Aufrufer / Aufgerufene:** Aufgerufen von `test_agent.py`, `test_tenant_isolation.py`, `conftest`-nahe Fixtures.
