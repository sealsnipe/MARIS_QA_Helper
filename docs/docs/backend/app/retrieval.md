# `backend/app/retrieval.py`

**Quellpfad:** `backend/app/retrieval.py`

## Zweck und logischer Aufbau

Schicht zwischen **Agent/Chat** und **Qdrant-Vektorstore**: wandelt Suchanfragen in Embeddings, holt Treffer pro Mandant (oder mandantenübergreifend), filtert nach Mindest-Score und bereitet Treffer für den LLM-Kontext sowie die Quellenanzeige im UI auf.

Lesereihenfolge: Dataclass `RetrievalHit` → Hilfsfunktion `clamp_top_k` → Kernfunktion `search_knowledge_base` → mandantenspezifische Varianten (`search_knowledge_base_scoped`, `search_knowledge_base_all`) → Mapping `_filter_hits` → Formatierung `format_hits_for_model` → Quellenregister `SourceRegistry` → Zitationsfilter `filter_sources_by_answer_citations`.

Im Request-Flow: Der Agent ruft typischerweise `search_knowledge_base_scoped` auf; die Treffer werden per `format_hits_for_model` in den Prompt eingebettet und parallel in `SourceRegistry` für die API-Antwort gesammelt. Nach der Modellantwort filtert `filter_sources_by_answer_citations` die angezeigten Quellen auf tatsächlich zitierte Nummern.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.customers`: `GLOBAL_CUSTOMER_ID`, `is_global_customer`
  - `app.config`: `get_settings` (`TOP_K_DEFAULT`, `MIN_SCORE_DEFAULT`)
  - `app.embeddings`: `EmbeddingsBackend`, `get_embeddings_backend`
  - `app.prompts`: `NO_HITS_TEXT`
  - `app.qdrant_store`: `SearchHit`, `VectorStore`, `get_vector_store`
- **Wird genutzt von:**
  - `backend/app/agent.py` — RAG-Suche und Quellenaufbereitung
  - `backend/app/routes.py` — `filter_sources_by_answer_citations` nach Chat-Antwort
- **HTTP / UI:** indirekt über `/api/chat` (Quellen in Antwort)
- **Daten:** Qdrant-Collections pro `customer_id`; Payload-Felder `document_id`, `title`, `chunk_index`, `text`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `RetrievalHit` | Dataclass | Normalisierter Suchtreffer mit `document_id`, `title`, `chunk_index`, `text`, `score` |
| `_CITATION_PATTERN` | Regex (`re.compile`) | Erkennt Zitationsmarker `[1]`, `[2]`, … in Modellantworten |

## Funktionen und Klassen

### `clamp_top_k(top_k: int | None, default: int) -> int`

**Beschreibung:** Begrenzt `top_k` auf 1–20; `None` wird durch `default` ersetzt.

**Parameter / Rückgabe:** `top_k` optional; `default` Fallback. Rückgabe: geklemmter Integer.

**Ablauf / lokale Variablen:** `value` — effektiver Wert vor Clamping.

**Aufrufer / Aufgerufene:** Von allen `search_knowledge_base*`-Funktionen genutzt.

---

### `search_knowledge_base(customer_id, query, top_k=None, *, min_score=None, embeddings=None, vector_store=None) -> list[RetrievalHit]`

**Beschreibung:** Einzelne Vektorsuche in der Qdrant-Collection eines Mandanten.

**Parameter / Rückgabe:** Mandanten-ID, Suchtext, optionales `top_k` und `min_score`; injizierbare Backends. Rückgabe: gefilterte `RetrievalHit`-Liste.

**Ablauf / lokale Variablen:** `settings`, `limit`, `threshold`, `vector` (Query-Embedding), `raw_hits` (Qdrant-Rohresultate).

**Aufrufer / Aufgerufene:** Ruft `get_settings`, `get_embeddings_backend`, `get_vector_store`, `embeddings.embed_query`, `vector_store.search`, `_filter_hits` auf. Wird von `search_knowledge_base_scoped` und `search_knowledge_base_all` aufgerufen.

---

### `search_knowledge_base_scoped(customer_id, query, top_k=None, *, scope_customer_ids=None, min_score=None, embeddings=None, vector_store=None) -> list[RetrievalHit]`

**Beschreibung:** Mandantenabhängige Suche: Global-Modus delegiert an `search_knowledge_base_all`; sonst Merge aus globaler und kundenspezifischer KB.

**Parameter / Rückgabe:** `scope_customer_ids` — zusätzliche Mandanten im Global-Modus. Rückgabe: deduplizierte, score-sortierte Treffer (max. `limit`).

**Ablauf / lokale Variablen:** `global_limit` (`limit // 2`), `customer_limit`, `merged` (Dict keyed by `(document_id, chunk_index)`), `ordered`.

**Aufrufer / Aufgerufene:** Bei Global-Kunde → `search_knowledge_base_all`; sonst zwei Aufrufe von `search_knowledge_base` (global + Kunde), Merge nach höchstem Score.

---

### `search_knowledge_base_all(customer_ids, query, top_k=None, *, min_score=None, embeddings=None, vector_store=None) -> list[RetrievalHit]`

**Beschreibung:** Suche über globale Collection plus angegebene Mandanten-IDs (Admin/Global-Ansicht).

**Parameter / Rückgabe:** Liste von Mandanten-IDs (ohne Duplikate neben `GLOBAL_CUSTOMER_ID`). Rückgabe: top `limit` Treffer über alle Collections.

**Ablauf / lokale Variablen:** `per_collection_limit` (2–3), `search_ids`, `merged`, `ordered`.

**Aufrufer / Aufgerufene:** Iteriert `search_knowledge_base` pro Collection; dedupliziert wie oben.

---

### `_filter_hits(raw_hits: list[SearchHit], min_score: float) -> list[RetrievalHit]`

**Beschreibung:** Mappt Qdrant-`SearchHit` auf `RetrievalHit` und verwirft Treffer unter `min_score`.

**Parameter / Rückgabe:** Roh-Treffer und Schwellwert. Rückgabe: Liste `RetrievalHit`.

**Ablauf / lokale Variablen:** `hits`, `payload` pro Item; Default-Titel `"Unbekannt"`.

**Aufrufer / Aufgerufene:** Nur von `search_knowledge_base`.

---

### `format_hits_for_model(hits: list[RetrievalHit], start_index: int = 1) -> str`

**Beschreibung:** Serialisiert Treffer als nummerierten Kontextblock für den System-/User-Prompt des Agents.

**Parameter / Rückgabe:** Trefferliste, Startnummer für Zitationen. Leere Liste → `NO_HITS_TEXT`.

**Ablauf / lokale Variablen:** `parts` — Zeilen mit `[n] Quelle: "…" · Abschnitt …`.

**Aufrufer / Aufgerufene:** Agent-Modul; nutzt `NO_HITS_TEXT` aus `app.prompts`.

---

### Klasse `SourceRegistry`

Registriert Treffer in stabiler Reihenfolge für die API-Quellenliste (`n`, `document_id`, `title`, …).

| Attribut | Typ | Beschreibung |
|---|---|---|
| `_items` | `dict[tuple[str, int], RetrievalHit]` | Treffer keyed by `(document_id, chunk_index)` |
| `_order` | `list[tuple[str, int]]` | Einfügereihenfolge |

#### `__init__(self) -> None`

Initialisiert leere `_items` und `_order`.

#### `register(self, hits: list[RetrievalHit]) -> None`

Fügt neue Treffer hinzu (bestehende Keys werden nicht überschrieben).

#### `has_hits` (`@property`) -> `bool`

`True`, wenn mindestens ein Treffer registriert ist.

#### `ordered_sources(self) -> list[dict[str, Any]]`

Liefert Quellen-Dicts mit `n`, `document_id`, `title`, `chunk_index`, `score` (gerundet auf 4 Dezimalen).

---

### `filter_sources_by_answer_citations(sources: list[dict[str, Any]], answer: str) -> list[dict[str, Any]]`

**Beschreibung:** Filtert Quellen auf im Antworttext zitierte `[n]`-Marker; ohne Zitationen nur der stärkste Treffer.

**Parameter / Rückgabe:** Quellenliste (mit Feld `n`) und Modellantwort. Rückgabe: gefilterte Quellen.

**Ablauf / lokale Variablen:** `cited_numbers`, `seen`, `cited_set`; Fallback: `max(sources, key=score)`.

**Aufrufer / Aufgerufene:** `routes.api_chat` nach `run_agent`; nutzt `_CITATION_PATTERN`.
