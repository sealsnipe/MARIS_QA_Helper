# 06 — Agent- & RAG-Design

**Stand:** 2026-06-02 · **Status:** verbindlich für MVP

Herzstück. Der Agent ist **fest an den aktiven Kunden gebunden** und durchsucht nur dessen
Collection `kb_{customer_id}`.

---

## 1. Philosophie: agentisch statt starr

Das Modell bekommt **ein Werkzeug** und entscheidet selbst, ob/wie oft es sucht. Vorteile:
mehrteilige Fragen → mehrere Suchen; triviale Fragen → ggf. keine Suche; klarer Andockpunkt für
weitere Tools (z. B. `search_jira`) später. Begrenzt durch `MAX_TOOL_ROUNDS`.

## 2. Mandanten-Bindung (Invariant)

- `agent.run(customer_id, message, top_k)` bekommt `customer_id` **aus der Session** (über
  `get_current_customer`), **nicht** vom Modell oder Client.
- Das Tool `search_knowledge_base` sucht **ausschließlich** in `kb_{customer_id}`. Das Modell
  sieht keine fremden Collections und kann den Kunden nicht wechseln („kein Tenant-Hopping").
- `customer_id` ist **kein** Tool-Parameter — er ist serverseitig injiziert.

## 3. Tool `search_knowledge_base`

```json
{
  "type": "function",
  "function": {
    "name": "search_knowledge_base",
    "description": "Durchsucht die Wissensdatenbank des aktuellen Kunden nach passenden Textstellen. Nutze dies, bevor du inhaltliche Aussagen triffst. Mehrfach mit verschiedenen Suchbegriffen möglich.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": { "type": "string", "description": "Suchanfrage in natürlicher Sprache oder Stichworten." },
        "top_k": { "type": "integer", "description": "Anzahl Treffer (1-20).", "default": 6 }
      },
      "required": ["query"]
    }
  }
}
```
Tool-Ausführung (serverseitig, `customer_id` aus Closure/Session):
```text
1. embeddings.embed_query(query)
2. qdrant.search(customer_id, query_vector, top_k)      # nur kb_{customer_id}
3. filtern: score >= MIN_SCORE_DEFAULT
4. Treffer in session-weiter sources-Sammlung registrieren (für Citations)
5. nummerierte, kompakte Liste an das Modell zurückgeben (§5)
```

## 4. Agent-Loop

```python
def run(customer_id: str, message: str, top_k: int) -> ChatResult:
    messages = [{"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":message}]
    collected: dict[tuple,Source] = {}
    any_hits = False
    for _ in range(MAX_TOOL_ROUNDS):
        resp = llm.chat(messages, tools=[SEARCH_TOOL])
        if resp.tool_calls:
            messages.append(resp.assistant_message)
            for call in resp.tool_calls:
                hits = search_kb(customer_id, call.args.query, call.args.top_k or top_k)
                if hits: any_hits = True; register(collected, hits)
                messages.append(tool_result(call.id, format_hits(hits)))
            continue
        if not any_hits:
            return ChatResult(NO_CONTEXT_TEXT, [], no_context=True)
        return ChatResult(resp.content, ordered_sources(collected), no_context=False)
    final = llm.chat(messages, tools=[])     # letzte Runde ohne Tools erzwingt Antwort
    if not any_hits:
        return ChatResult(NO_CONTEXT_TEXT, [], no_context=True)
    return ChatResult(final.content, ordered_sources(collected), no_context=False)
```
Guardrails: `MAX_TOOL_ROUNDS` (Default 4); letzte Runde ohne Tools; `collected` dedupliziert über
`(document_id, chunk_index)` und nummeriert stabil.

## 5. Format der Tool-Ergebnisse an das Modell
```text
[1] Quelle: "VPN Runbook" · Abschnitt 4
<chunk text>

[2] Quelle: "Eskalation" · Abschnitt 1
<chunk text>
```
Keine Treffer über Schwelle → `"Keine passenden Treffer in der Wissensdatenbank."`

## 6. System-Prompt (verbindlicher Wortlaut)
```text
Du bist der Support-Wissensassistent von SUP_QA_Helper.

Regeln:
- Beantworte Fragen ausschließlich auf Basis der Wissensdatenbank des aktuellen Kunden,
  die dir das Tool "search_knowledge_base" liefert. Nutze das Tool, bevor du inhaltliche
  Aussagen triffst.
- Du darfst das Tool mehrfach mit unterschiedlichen Suchbegriffen aufrufen, wenn das hilft.
- Wenn die Suchergebnisse die Frage nicht abdecken, sage ehrlich, dass die Wissensdatenbank
  dazu keine belastbare Quelle enthält. Erfinde nichts und rate nicht.
- Erfinde keine Quellen. Beziehe dich nur auf die nummerierten Treffer des Tools.
- Kennzeichne genutzte Treffer im Text mit ihrer Nummer in eckigen Klammern, z. B. [1], [2].
- Fasse dich klar und konkret. Schritte als Liste.
- Antworte auf Deutsch.
```
> Hinweis: Der Kunden-Scope ist **technisch** erzwungen (das Tool sieht nur `kb_{customer_id}`).
> Der Prompt-Hinweis „des aktuellen Kunden" ist zusätzliche Klarheit, **nicht** die Garantie.

## 7. No-Context-Verhalten
Kein Treffer ≥ `MIN_SCORE_DEFAULT` über alle Suchen → **ohne** weiteren LLM-Call:
```text
Ich habe in der Wissensdatenbank dazu keine belastbare Quelle gefunden.
```
(Konstante `NO_CONTEXT_TEXT` in `prompts.py`.)

## 8. Citations (deterministisch)
Quellen nur aus abgerufenen Treffern (`collected`), nie aus freiem Modelltext (FR-15, ADR-4).
Felder: `n`, `document_id`, `title`, `chunk_index`, `score`. UI rendert Liste unter der Antwort;
`[n]` korrespondiert mit `sources[n]`.

## 9. Chunking (`chunking.py`)
- Normalisierung (Whitespace/Leerzeilen), Split bevorzugt an Absatz-/Überschriftgrenzen.
- Ziel ~3500 Zeichen (~900 Tokens), Overlap ~400 Zeichen (~100 Tokens), keine leeren Chunks.
- Identisch für Text-Eingabe **und** aus Dateien extrahierten Text (gleicher Kern).

## 10. Embeddings (`embeddings.py`)
- `text-embedding-3-small`, dim 1536. `embed_documents(list)` (batched) / `embed_query(text)`.
- Fehlt Key → klarer Fehler. In Tests **gemockt** (deterministische Fake-Vektoren), keine echten Calls.
- Hinweis: bei späterem Wechsel auf e5/bge-m3 query/passage-Prefixe + Collection-Neuanlage beachten.

## 11. Retrieval-Parameter
| Parameter | Default | Env | Bemerkung |
|---|---|---|---|
| `top_k` | 6 | `TOP_K_DEFAULT` | pro Suche; Clamp 1..20 |
| `min_score` | 0.25 | `MIN_SCORE_DEFAULT` | Cosine; **empirisch tunen** mit Demo-Inhalt |
| `max_tool_rounds` | 4 | `MAX_TOOL_ROUNDS` | Loop-Begrenzung |

## 12. Erweiterungspunkt
Tool-agnostischer Loop. Späteres `search_jira(jql)` als zusätzliches Tool; Citation-Sammlung
identisch (`source_type="jira"`, `source_url`). Siehe `12_roadmap.md`.
