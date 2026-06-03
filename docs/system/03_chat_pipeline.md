# 03 — Chat-Pipeline

**Stand:** 2026-06-03

---

## End-to-End

```text
Browser (chat.html + app.js)
  POST /api/chat { message, chat_id?, top_k? }
    → get_current_user + get_current_customer
    → chats: Session laden/erzeugen, User-Nachricht speichern
    → agent.run(customer_id, message, db, scope_customer_ids)
         → system_prompts: get_effective_system_prompt
         → llm.chat + Tool search_knowledge_base
         → retrieval.search_knowledge_base_scoped
         → qdrant_store.search (kb_{customer_id}, ggf. kb_global)
    → filter_sources_by_answer_citations
    → chats: Assistant-Nachricht + sources_json speichern
  JSON { answer, sources, no_context, chat_id, chat_title }
    → app.js: Markdown rendern, Quellen anzeigen
```

---

## Chat-Sessions

| API | Zweck |
|---|---|
| `GET/POST /api/chats` | Liste / neuer Chat pro User+Mandant |
| `GET /api/chats/{id}` | Verlauf inkl. Messages |
| `DELETE /api/chats/{id}` | Chat löschen |
| `POST /api/chat` | Nachricht senden (legt Chat an wenn kein `chat_id`) |

Isolation: `get_session_for_user` prüft `user_id` **und** `customer_id`.

Spiegel: `chats.md`, `routes.md`

---

## Agent-Loop (`agent.run`)

1. System-Prompt aus DB (global + mandantenspezifisch + Hints)
2. Bis `MAX_TOOL_ROUNDS`: LLM mit `SEARCH_TOOL`
3. Bei Tool-Call: `search_knowledge_base_scoped`
4. `SourceRegistry` sammelt Treffer, nummeriert für Zitate `[1]`, `[2]`
5. Finale Antwort → nur zitierte Quellen in `sources` (oder bester Treffer als Fallback)

Spiegel: `agent.md`, `prompts.md`, `retrieval.md`, `llm.md`

---

## Global-Mandant vs Tenant

| Aktiver Kunde | Suche |
|---|---|
| Normal (`bglu`) | `kb_global` (limit/2) + `kb_bglu`, merged by score |
| `global` | `kb_global` + alle zugewiesenen Mandanten-KBs des Users |

`scope_customer_ids` kommt aus `list_assigned_customer_ids` — nur vom Server.

Spiegel: `retrieval.md`, `customers.md`

---

## Kein Kontext

Wenn keine Treffer über `MIN_SCORE_DEFAULT` oder LLM liefert nichts:  
Antwort = `NO_CONTEXT_TEXT`, `no_context: true`, leere `sources`.

---

## Betroffene Spiegel-Dateien

`templates/chat.md`, `static/app.md`, `routes.md`, `agent.md`, `chats.md`, `retrieval.md`, `system_prompts.md`, `prompts.md`, `llm.md`, `qdrant_store.md`
