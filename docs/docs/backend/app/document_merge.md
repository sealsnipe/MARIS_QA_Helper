# `backend/app/document_merge.py`

**Quellpfad:** `backend/app/document_merge.py`

## Zweck und logischer Aufbau

LLM- + heuristik-gestützte Merge-Vorschau und Apply für Admin-KB-Dokumente (bestehend vs. neuer Inhalt). Ermöglicht semantisches Zusammenführen mit Block-Auswahl (unchanged/modified/added/removed), Confidence-Scoring und optionalem LLM-Vorschlag.

Lesereihenfolge: Konstanten (VALID_BLOCK_KINDS, MERGE_LLM_SYSTEM_PROMPT) → Hilfs (cosine, align, compose, truncate, extract_json, guidance) → `build_merge_preview` (heuristic) → `llm_suggest_merge` → `evaluate...` / `finalize` → `merge_preview_for_documents` + `apply_document_merge` (mit client-selections + update_document_content).

Rolle: Post-Ingestion-Admin-Tool (kein automatisches Merge bei Upload); schützt bestehendes Wissen bei Updates.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.chunking` (MIN_TEXT_LENGTH, normalize_text, split_paragraph_blocks)
  - `app.config.get_settings`
  - `app.embeddings` (EmbeddingsBackend)
  - `app.ingestion` (IngestionError, get_document_text, update_document_content)
  - `app.llm` (LLMBackend, get_llm, get_similarity_llm)
  - `app.qdrant_store` (VectorStore)
- **Wird genutzt von:** `routes.py` (Admin-KB Merge-Endpoints: Preview + Apply), Tests (`test_document_merge.py`)
- **HTTP / UI:** Admin-Knowledge Edit-Flow (Inspect → Merge-Vorschau → Block-Select → Apply); JSON `/api/admin/...`
- **Daten:** SQLite `documents` + `chunks`; Qdrant (via update); customer-scoped.

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `VALID_BLOCK_KINDS` | frozenset | `{"unchanged", "modified", "added", "removed"}` |
| `MERGE_LLM_SYSTEM_PROMPT` | str | Strenger JSON-only Prompt für Merge-Blöcke (exakte Zitate, Regeln pro Kind) |

## Funktionen und Klassen

### `MergeError(code: str, detail: str | None = None)`

Exception-Klasse für Merge-spezifische Fehler (llm_*, empty_text, not_found, invalid_blocks, ...). Wird in routes zu 4xx/5xx gemappt.

### `cosine_similarity(a: list[float], b: list[float]) -> float`

Einfache Cosine-Ähnlichkeit (0 bei Längenfehler oder Zero-Vektor).

### `align_block_pairs(...) -> tuple[dict[int, tuple[int, float]], set[int]]`

Heuristische 1:1-Zuordnung neuer Blöcke zu alten via Embeddings + min_score. Markiert used_old.

### `compose_merged_text(blocks, selections) -> str`

Baut finalen Text aus ausgewählten Blöcken (inkl. modified/added/removed-Logik).

### `llm_suggest_merge(...) -> dict`

Ruft Similarity-LLM mit truncatem Prompt + Heuristik-Hint; parst JSON (mit Fallback-Extract); normalisiert Blöcke; liefert Preview + Stats + llm_summary.

### `build_merge_preview(...) -> dict`

Heuristik-Pfad: split → align → emit unchanged/modified/removed + anchored added → Stats + merged_preview. Kein LLM.

### `merge_preview_for_documents(db, customer_id, target_document_id, new_text, *, use_llm=False, ...) -> dict`

Liest Ziel-Dok via `get_document_text`; baut heuristic (ggf. LLM); target_*-Felder.

### `apply_document_merge(...) -> dict`

Validiert Selections (oder Fallback), composed/override Text; ruft `update_document_content` (re-chunk/embed/upsert); liefert neues Doc + Stats.

### `validate_merge_text(text) -> str`

Prüft MIN_TEXT_LENGTH nach normalize.

Weitere Hilfs: `_truncate_for_llm`, `_extract_json_object`, `_normalize_llm_blocks`, `_blocks_from_client_payload`, `evaluate_merge_confidence`, `finalize_merge_preview`.
