from __future__ import annotations

import json
import math
import re
from typing import Any

from sqlalchemy.orm import Session

from app.chunking import MIN_TEXT_LENGTH, normalize_text, split_paragraph_blocks
from app.config import get_settings
from app.embeddings import EmbeddingsBackend, get_embeddings_backend
from app.ingestion import IngestionError, get_document_text, update_document_content
from app.llm import LLMBackend, LLMError, get_llm, get_similarity_llm
from app.qdrant_store import VectorStore, get_vector_store

VALID_BLOCK_KINDS = frozenset({"unchanged", "modified", "added", "removed"})

MERGE_LLM_SYSTEM_PROMPT = """Du hilfst Redakteuren beim Zusammenführen von Wissensdokumenten.
Antworte ausschließlich mit validem JSON — kein Markdown, kein Fließtext außerhalb des JSON.

Schema:
{
  "summary": "1–2 Sätze auf Deutsch: Was sich geändert hat und was empfohlen wird",
  "blocks": [
    {
      "kind": "unchanged|modified|added|removed",
      "old_text": "string oder null",
      "new_text": "string oder null",
      "include": true,
      "hint": "Kurzer Hinweis für den Nutzer (optional)"
    }
  ]
}

Regeln:
- Nutze exakte Textzitate aus BESTEHEND und NEU — nichts erfinden.
- unchanged: gleicher Inhalt, old_text setzen.
- modified: inhaltlich verwandte Absätze; include=true → new_text übernehmen.
- added: nur in NEU; include=true → einfügen.
- removed: nur in BESTEHEND; include=false → behalten, include=true → streichen.
- Reihenfolge der blocks = empfohlene Dokument-Reihenfolge nach Merge.
- Bei Bild-Platzhaltern [BILD …] unverändert übernehmen."""


class MergeError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def align_block_pairs(
    old_blocks: list[str],
    new_blocks: list[str],
    *,
    embeddings: EmbeddingsBackend,
    min_score: float,
) -> tuple[dict[int, tuple[int, float]], set[int]]:
    if not new_blocks:
        return {}, set()

    new_vectors = embeddings.embed_documents(new_blocks)
    old_vectors = embeddings.embed_documents(old_blocks) if old_blocks else []
    used_old: set[int] = set()
    mapping: dict[int, tuple[int, float]] = {}

    for j, new_vec in enumerate(new_vectors):
        best_i: int | None = None
        best_score = -1.0
        for i, old_vec in enumerate(old_vectors):
            if i in used_old:
                continue
            score = cosine_similarity(new_vec, old_vec)
            if score > best_score:
                best_score = score
                best_i = i
        if best_i is not None and best_score >= min_score:
            mapping[j] = (best_i, best_score)
            used_old.add(best_i)
    return mapping, used_old


def _suggested_after_old_index(j: int, new_to_old: dict[int, tuple[int, float]]) -> int:
    for k in range(j - 1, -1, -1):
        if k in new_to_old:
            return new_to_old[k][0]
    return -1


def _default_include(kind: str) -> bool | None:
    if kind == "modified":
        return True
    if kind == "added":
        return True
    if kind == "removed":
        return False
    return None


def compose_merged_text(blocks: list[dict[str, Any]], selections: dict[str, bool | None]) -> str:
    parts: list[str] = []
    for block in blocks:
        kind = block["kind"]
        block_id = block["id"]
        include = selections.get(block_id)
        if include is None:
            include = block.get("include")

        if kind == "unchanged":
            text = block.get("old_text") or block.get("new_text")
            if text:
                parts.append(text)
        elif kind == "modified":
            if include:
                if block.get("new_text"):
                    parts.append(block["new_text"])
            elif block.get("old_text"):
                parts.append(block["old_text"])
        elif kind == "added":
            if include and block.get("new_text"):
                parts.append(block["new_text"])
        elif kind == "removed" and not include and block.get("old_text"):
            parts.append(block["old_text"])
    return "\n\n".join(parts)


def _truncate_for_llm(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head - 20
    return f"{text[:head]}\n\n[… gekürzt …]\n\n{text[-tail:]}"


def _extract_json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise MergeError("llm_invalid_response") from None
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise MergeError("llm_invalid_response")
    return parsed


def _guidance_message(*, needs_llm_assist: bool, source: str, confidence: float) -> str:
    if source == "llm":
        return "KI-Vorschlag aktiv — prüfe die markierten Abschnitte und gehe dann zur Vorschau."
    if needs_llm_assist:
        return (
            "Die automatische Zuordnung ist unsicher (stark umstrukturierter Text). "
            "Lade einen KI-Vorschlag — der ordnet Absätze semantisch zu."
        )
    if confidence >= 0.85:
        return "Automatischer Abgleich sieht gut aus. Prüfe kurz die markierten Änderungen."
    return "Einige Abschnitte wurden neu zugeordnet — bitte kurz gegenlesen, dann zur Vorschau."


def evaluate_merge_confidence(preview: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    stats = preview.get("stats") or {}
    old_count = int(preview.get("old_block_count") or 0)
    matched = int(preview.get("matched_old_blocks") or 0)
    total_blocks = max(
        sum(stats.get(key, 0) for key in ("unchanged", "modified", "added", "removed")),
        1,
    )
    disruptive = int(stats.get("added", 0)) + int(stats.get("removed", 0))
    match_ratio = matched / max(old_count, 1)
    disruptive_ratio = disruptive / total_blocks
    confidence = min(1.0, match_ratio * 0.55 + (1 - disruptive_ratio) * 0.45)
    needs_llm_assist = settings.MERGE_LLM_ENABLED and (
        confidence < settings.MERGE_LLM_MIN_CONFIDENCE
        or disruptive_ratio >= 0.35
        or (old_count >= 3 and matched <= 1)
    )
    source = preview.get("source") or "heuristic"
    if source == "llm":
        needs_llm_assist = False
    return {
        "confidence": round(confidence, 3),
        "needs_llm_assist": needs_llm_assist,
        "llm_available": settings.MERGE_LLM_ENABLED,
        "guidance": _guidance_message(
            needs_llm_assist=needs_llm_assist,
            source=source,
            confidence=confidence,
        ),
    }


def _normalize_llm_blocks(raw_blocks: list[Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for index, item in enumerate(raw_blocks):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "unchanged").strip().lower()
        if kind not in VALID_BLOCK_KINDS:
            kind = "modified"
        include = item.get("include")
        if include is None:
            include = _default_include(kind)
        blocks.append(
            {
                "id": f"b{index}",
                "kind": kind,
                "old_text": item.get("old_text"),
                "new_text": item.get("new_text"),
                "score": None,
                "include": include,
                "hint": (item.get("hint") or "").strip() or None,
                "source": "llm",
            }
        )
    if not blocks:
        raise MergeError("llm_invalid_response")
    return blocks


def llm_suggest_merge(
    old_text: str,
    new_text: str,
    *,
    heuristic: dict[str, Any] | None = None,
    llm: LLMBackend | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.MERGE_LLM_ENABLED:
        raise MergeError("llm_disabled")

    llm = llm or get_similarity_llm(db=db)
    max_chars = settings.MERGE_LLM_MAX_CHARS
    heuristic_hint = ""
    if heuristic and heuristic.get("stats"):
        stats = heuristic["stats"]
        heuristic_hint = (
            f"\n\nHeuristik-Vorschlag: {stats.get('modified', 0)} geändert, "
            f"{stats.get('added', 0)} neu, {stats.get('removed', 0)} entfernt, "
            f"{stats.get('unchanged', 0)} unverändert."
        )

    user_prompt = (
        "Führe BESTEHEND und NEU zu einem sinnvollen Wissensdokument zusammen.\n\n"
        f"=== BESTEHEND ===\n{_truncate_for_llm(old_text, max_chars // 2)}\n\n"
        f"=== NEU ===\n{_truncate_for_llm(new_text, max_chars // 2)}"
        f"{heuristic_hint}"
    )

    try:
        response = llm.chat(
            [
                {"role": "system", "content": MERGE_LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
    except LLMError as exc:
        raise MergeError("llm_failed", detail=str(exc)) from exc

    raw_content = (response.content or "").strip()
    if not raw_content:
        raise MergeError("llm_empty_response")

    try:
        payload = _extract_json_object(raw_content)
    except (json.JSONDecodeError, MergeError) as exc:
        raise MergeError("llm_invalid_response", detail=str(exc)) from exc

    summary = str(payload.get("summary") or "").strip()
    raw_blocks = payload.get("blocks")
    if not isinstance(raw_blocks, list):
        raise MergeError("llm_invalid_response")

    blocks = _normalize_llm_blocks(raw_blocks)
    selection_defaults = {block["id"]: block.get("include") for block in blocks}
    merged_preview = compose_merged_text(blocks, selection_defaults)
    if len(normalize_text(merged_preview)) < MIN_TEXT_LENGTH:
        raise MergeError("llm_empty_response")

    stats = {
        "unchanged": sum(1 for block in blocks if block["kind"] == "unchanged"),
        "modified": sum(1 for block in blocks if block["kind"] == "modified"),
        "added": sum(1 for block in blocks if block["kind"] == "added"),
        "removed": sum(1 for block in blocks if block["kind"] == "removed"),
    }
    preview = {
        "blocks": blocks,
        "merged_preview": merged_preview,
        "stats": stats,
        "old_block_count": len(split_paragraph_blocks(old_text)),
        "new_block_count": len(split_paragraph_blocks(new_text)),
        "matched_old_blocks": stats["unchanged"] + stats["modified"],
        "source": "llm",
        "llm_summary": summary or None,
    }
    preview.update(evaluate_merge_confidence(preview))
    return preview


def _blocks_from_client_payload(
    block_selections: list[dict[str, Any]],
    *,
    fallback_preview: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, bool | None]]:
    if block_selections and block_selections[0].get("kind"):
        blocks: list[dict[str, Any]] = []
        selection_map: dict[str, bool | None] = {}
        for index, item in enumerate(block_selections):
            block_id = str(item.get("id") or f"b{index}")
            kind = item.get("kind") or "unchanged"
            blocks.append(
                {
                    "id": block_id,
                    "kind": kind,
                    "old_text": item.get("old_text"),
                    "new_text": item.get("new_text"),
                    "include": item.get("include"),
                    "hint": item.get("hint"),
                    "source": item.get("source"),
                }
            )
            selection_map[block_id] = item.get("include")
        return blocks, selection_map

    if fallback_preview is None:
        return [], {}
    selection_map = {
        str(item["id"]): item.get("include")
        for item in block_selections
        if isinstance(item, dict) and item.get("id")
    }
    return list(fallback_preview.get("blocks") or []), selection_map


def build_merge_preview(
    old_text: str,
    new_text: str,
    *,
    embeddings: EmbeddingsBackend | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    normalized_old = normalize_text(old_text)
    normalized_new = normalize_text(new_text)
    if len(normalized_new) < MIN_TEXT_LENGTH:
        raise MergeError("empty_text")
    if len(normalized_old) < MIN_TEXT_LENGTH:
        raise MergeError("target_empty")

    old_blocks = split_paragraph_blocks(normalized_old)
    new_blocks = split_paragraph_blocks(normalized_new)
    embeddings = embeddings or get_embeddings_backend()
    new_to_old, used_old = align_block_pairs(
        old_blocks,
        new_blocks,
        embeddings=embeddings,
        min_score=settings.MERGE_BLOCK_MIN_SCORE,
    )
    old_to_new = {old_i: new_j for new_j, (old_i, _) in new_to_old.items()}

    blocks: list[dict[str, Any]] = []
    block_id = 0

    def make_id() -> str:
        nonlocal block_id
        bid = f"b{block_id}"
        block_id += 1
        return bid

    added_by_anchor: dict[int, list[dict[str, Any]]] = {}
    for j, new_block in enumerate(new_blocks):
        if j in new_to_old:
            continue
        anchor = _suggested_after_old_index(j, new_to_old)
        added_by_anchor.setdefault(anchor, []).append(
            {
                "id": make_id(),
                "kind": "added",
                "old_text": None,
                "new_text": new_block,
                "score": None,
                "include": True,
                "suggested_after_index": anchor,
            }
        )

    def emit_old_block(i: int) -> None:
        if i in old_to_new:
            j = old_to_new[i]
            old_block = old_blocks[i]
            new_block = new_blocks[j]
            score = new_to_old[j][1]
            if normalize_text(old_block) == normalize_text(new_block):
                kind = "unchanged"
            else:
                kind = "modified"
            blocks.append(
                {
                    "id": make_id(),
                    "kind": kind,
                    "old_text": old_block,
                    "new_text": new_block,
                    "score": round(score, 4),
                    "include": _default_include(kind),
                    "old_index": i,
                    "new_index": j,
                }
            )
        else:
            blocks.append(
                {
                    "id": make_id(),
                    "kind": "removed",
                    "old_text": old_blocks[i],
                    "new_text": None,
                    "score": None,
                    "include": False,
                    "old_index": i,
                    "new_index": None,
                }
            )

    blocks.extend(added_by_anchor.get(-1, []))
    for i in range(len(old_blocks)):
        emit_old_block(i)
        blocks.extend(added_by_anchor.get(i, []))

    selection_defaults = {block["id"]: block.get("include") for block in blocks}
    merged_preview = compose_merged_text(blocks, selection_defaults)
    stats = {
        "unchanged": sum(1 for block in blocks if block["kind"] == "unchanged"),
        "modified": sum(1 for block in blocks if block["kind"] == "modified"),
        "added": sum(1 for block in blocks if block["kind"] == "added"),
        "removed": sum(1 for block in blocks if block["kind"] == "removed"),
    }

    return {
        "blocks": blocks,
        "merged_preview": merged_preview,
        "stats": stats,
        "old_block_count": len(old_blocks),
        "new_block_count": len(new_blocks),
        "matched_old_blocks": len(used_old),
        "source": "heuristic",
    }


def finalize_merge_preview(preview: dict[str, Any]) -> dict[str, Any]:
    preview.update(evaluate_merge_confidence(preview))
    return preview


def merge_preview_for_documents(
    db: Session,
    customer_id: str,
    target_document_id: str,
    new_text: str,
    *,
    use_llm: bool = False,
    embeddings: EmbeddingsBackend | None = None,
    llm: LLMBackend | None = None,
) -> dict[str, Any]:
    resolved = get_document_text(db, customer_id, target_document_id)
    if resolved is None:
        raise MergeError("not_found")
    document, old_text = resolved
    heuristic = build_merge_preview(old_text, new_text, embeddings=embeddings)
    if use_llm:
        preview = llm_suggest_merge(old_text, new_text, heuristic=heuristic, llm=llm, db=db)
    else:
        preview = finalize_merge_preview(heuristic)
    preview["target_document_id"] = document.id
    preview["target_title"] = document.title
    return preview


def apply_document_merge(
    db: Session,
    customer_id: str,
    target_document_id: str,
    new_text: str,
    block_selections: list[dict[str, Any]],
    *,
    title: str | None = None,
    merged_text_override: str | None = None,
    embeddings: EmbeddingsBackend | None = None,
    vector_store: VectorStore | None = None,
) -> dict[str, Any]:
    resolved = get_document_text(db, customer_id, target_document_id)
    if resolved is None:
        raise MergeError("not_found")
    document, old_text = resolved

    fallback_preview = build_merge_preview(old_text, new_text, embeddings=embeddings)
    blocks, selection_map = _blocks_from_client_payload(
        block_selections,
        fallback_preview=fallback_preview,
    )
    if not blocks:
        raise MergeError("invalid_blocks")

    if merged_text_override and merged_text_override.strip():
        merged_text = validate_merge_text(merged_text_override)
    else:
        merged_text = compose_merged_text(blocks, selection_map)
    if len(normalize_text(merged_text)) < MIN_TEXT_LENGTH:
        raise MergeError("empty_text")

    final_title = (title or document.title).strip()
    embeddings = embeddings or get_embeddings_backend()
    vector_store = vector_store or get_vector_store()
    try:
        result = update_document_content(
            db,
            customer_id,
            target_document_id,
            final_title,
            merged_text,
            embeddings=embeddings,
            vector_store=vector_store,
        )
    except IngestionError as exc:
        raise MergeError(exc.code, detail=exc.detail) from exc

    return {
        "document": result.document,
        "merged_text": merged_text,
        "stats": {
            "unchanged": sum(1 for block in blocks if block.get("kind") == "unchanged"),
            "modified": sum(1 for block in blocks if block.get("kind") == "modified"),
            "added": sum(1 for block in blocks if block.get("kind") == "added"),
            "removed": sum(1 for block in blocks if block.get("kind") == "removed"),
        },
    }


def validate_merge_text(text: str) -> str:
    normalized = normalize_text(text)
    if len(normalized) < MIN_TEXT_LENGTH:
        raise MergeError("empty_text")
    return normalized
