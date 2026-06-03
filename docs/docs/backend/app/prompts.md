# `backend/app/prompts.py`

**Quellpfad:** `backend/app/prompts.py`

## Zweck und logischer Aufbau

**Prompt-Konstanten und Tool-Schema** für den Support-Agenten. Enthält den Default-System-Prompt, Formatierungs- und Modus-Hinweise, Fallback-Texte bei fehlendem Kontext sowie die OpenAI-Function-Definition `search_knowledge_base`.

Lesereihenfolge: Docstring → mehrzeilige Prompt-Strings → Alias `SYSTEM_PROMPT` → Kurztexte `NO_CONTEXT_TEXT`, `NO_HITS_TEXT` → Dict `SEARCH_TOOL`.

`app.agent.run_chat` nutzt `DEFAULT_GLOBAL_SYSTEM_PROMPT` (bzw. effektiven Prompt aus DB) und übergibt `[SEARCH_TOOL]` an das LLM. `app.system_prompts` baut daraus den zusammengesetzten System-Prompt für Global- und Kundenmodus.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** keine Projektimports (reine Konstanten)
- **Wird genutzt von:** `backend/app/agent.py` (`DEFAULT_GLOBAL_SYSTEM_PROMPT`, `NO_CONTEXT_TEXT`, `SEARCH_TOOL`), `backend/app/system_prompts.py` (Prompt-Strings und Hints), `backend/app/retrieval.py` (`NO_HITS_TEXT`), Tests (`test_agent.py` — `NO_CONTEXT_TEXT`)
- **HTTP / UI / CLI:** indirekt über Chat-API; Tool-Name `search_knowledge_base` muss mit Agent- und Codex-LLM-Logik übereinstimmen
- **Daten:** keine

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `DEFAULT_GLOBAL_SYSTEM_PROMPT` | `str` (Mehrzeiler) | Standard-System-Prompt: nur KB-basierte Antworten, gezielte Suche, Quellenangaben `[1]`, `[2]`, Deutsch |
| `MARKDOWN_FORMATTING_HINT` | `str` | Anweisung für Markdown-Antworten (Überschriften, Tabellen, GFM) |
| `GLOBAL_MODE_HINT` | `str` | Hinweis für mandantenübergreifende Suche (Global-Modus) |
| `SYSTEM_PROMPT` | `str` | Alias für `DEFAULT_GLOBAL_SYSTEM_PROMPT` (Abwärtskompatibilität für Tests/Docs) |
| `NO_CONTEXT_TEXT` | `str` | Feste Assistant-Antwort wenn keine belastbare KB-Quelle gefunden wurde |
| `SEARCH_TOOL` | `dict` | OpenAI Tool-Schema für Function `search_knowledge_base` mit Parametern `query`, `top_k` |
| `NO_HITS_TEXT` | `str` | Text wenn Retrieval keine Treffer liefert (Tool-Ergebnis an LLM) |

## Funktionen und Klassen

Keine Funktionen oder Klassen — nur Modul-Konstanten.

### `SEARCH_TOOL` (Struktur)

**Beschreibung:** JSON-Schema für LLM Function Calling.

| Feld | Wert |
|---|---|
| `type` | `"function"` |
| `function.name` | `"search_knowledge_base"` |
| `function.parameters.properties.query` | `string`, required — Suchanfrage |
| `function.parameters.properties.top_k` | `integer`, default 4, Bereich 1–20 in Beschreibung |

**Aufrufer / Aufgerufene:** Übergeben an `llm.chat(..., tools=[SEARCH_TOOL])` in `agent.py`; von `CodexOAuthLLM` synthetisch nachgebildet.
