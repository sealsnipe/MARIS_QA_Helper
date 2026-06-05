from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.chunking import MIN_TEXT_LENGTH, normalize_text, validate_ingest_text
from app.llm import LLMBackend, LLMError, get_llm

REFINE_PRESET_CLARIFY = "clarify"
REFINE_PRESET_STRUCTURE = "structure"
REFINE_PRESET_SHORTEN = "shorten"
REFINE_PRESET_GRAMMAR = "grammar"

REFINE_PRESETS: dict[str, dict[str, str]] = {
    REFINE_PRESET_CLARIFY: {
        "label": "Klarer formulieren",
        "instruction": "Formuliere verständlicher und präziser, ohne neue Fakten.",
    },
    REFINE_PRESET_STRUCTURE: {
        "label": "Als KB-Artikel strukturieren",
        "instruction": "Strukturiere als KB-Artikel mit klaren Absätzen; ergänze passenden Titel und Summary.",
    },
    REFINE_PRESET_SHORTEN: {
        "label": "Kürzen",
        "instruction": "Verdichte den Text, entferne Redundanz, behalte alle Fakten.",
    },
    REFINE_PRESET_GRAMMAR: {
        "label": "Rechtschreibung & Grammatik",
        "instruction": "Korrigiere nur Rechtschreibung und Grammatik — minimal-invasive Änderungen.",
    },
}

DEFAULT_REFINE_PRESET = REFINE_PRESET_CLARIFY
MAX_CHANGE_RATIO = 0.45
VALID_CHANGE_KINDS = frozenset({"replace", "split", "merge", "insert", "delete"})

REFINE_SYSTEM_PROMPT = """Du überarbeitest Rohtext für eine interne Wissensdatenbank.
Antworte ausschließlich mit validem JSON — kein Markdown außerhalb des JSON.

Schema:
{
  "title": "string, max 200 Zeichen",
  "summary": "string, 1-3 Sätze",
  "keywords": ["string", "..."],
  "content": "vollständiger überarbeiteter Text",
  "changes": [
    {
      "id": "c1",
      "kind": "replace|split|merge|insert|delete",
      "sources": ["wörtliches Zitat aus dem ORIGINAL"],
      "target": "geänderter Abschnitt im überarbeiteten Text",
      "anchor": "kurzer eindeutiger Teilausschnitt aus target",
      "note": "optional, kurzer Hinweis auf Deutsch"
    }
  ]
}

Regeln:
- Keine neuen Fakten erfinden.
- Unveränderte Absätze wortgleich übernehmen.
- Nur geänderte Stellen in changes[] — jede change braucht sources (außer insert) und target.
- sources müssen exakte Substrings aus dem ORIGINAL sein (copy-paste).
- target und anchor müssen Substrings aus content sein.
- kind=split: ein Quell-Satz → mehrere Ziel-Sätze in target.
- kind=merge: mehrere Quell-Sätze → ein Ziel-Satz in target.
- Möglichst kleine, nachvollziehbare Änderungen."""


class ContentRefineError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code)


@dataclass
class ContentRefineResult:
    title: str
    summary: str
    keywords: list[str]
    content: str
    revision: dict[str, Any]


def list_refine_presets() -> list[dict[str, str]]:
    return [
        {"id": preset_id, "label": meta["label"]}
        for preset_id, meta in REFINE_PRESETS.items()
    ]


def _parse_json_response(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ContentRefineError("llm_invalid_response") from None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ContentRefineError("llm_invalid_response") from exc
    if not isinstance(parsed, dict):
        raise ContentRefineError("llm_invalid_response")
    return parsed


def _change_ratio(original: str, revised: str) -> float:
    if not original:
        return 1.0 if revised else 0.0
    from difflib import SequenceMatcher

    return 1.0 - SequenceMatcher(None, original, revised).ratio()


def _normalize_for_match(text: str) -> str:
    return normalize_text(text)


def validate_revision(
    original: str,
    revised: str,
    revision: dict[str, Any],
    *,
    max_change_ratio: float = MAX_CHANGE_RATIO,
) -> dict[str, Any]:
    ratio = _change_ratio(original, revised)
    changes = revision.get("changes")
    if not isinstance(changes, list):
        raise ContentRefineError("invalid_revision", "changes must be a list")

    normalized_original = _normalize_for_match(original)
    normalized_revised = _normalize_for_match(revised)
    validated_changes: list[dict[str, Any]] = []
    used_anchors: set[str] = set()

    for index, raw_change in enumerate(changes):
        if not isinstance(raw_change, dict):
            raise ContentRefineError("invalid_revision", f"change {index} invalid")
        kind = str(raw_change.get("kind", "replace")).strip().lower()
        if kind not in VALID_CHANGE_KINDS:
            raise ContentRefineError("invalid_revision", f"unknown kind {kind!r}")

        sources_raw = raw_change.get("sources") or []
        if isinstance(sources_raw, str):
            sources = [sources_raw.strip()] if sources_raw.strip() else []
        elif isinstance(sources_raw, list):
            sources = [str(item).strip() for item in sources_raw if str(item).strip()]
        else:
            sources = []

        target = str(raw_change.get("target", "")).strip()
        anchor = str(raw_change.get("anchor", "")).strip() or target[:80]
        note = str(raw_change.get("note", "")).strip() or None
        change_id = str(raw_change.get("id", f"c{index + 1}")).strip() or f"c{index + 1}"

        if kind != "insert":
            if not sources:
                raise ContentRefineError("invalid_revision", f"{change_id}: sources required")
            for source in sources:
                if source not in original and _normalize_for_match(source) not in normalized_original:
                    raise ContentRefineError("invalid_revision", f"{change_id}: source not in original")

        if kind != "delete":
            if not target or target not in revised:
                if _normalize_for_match(target) not in normalized_revised:
                    raise ContentRefineError("invalid_revision", f"{change_id}: target not in revised")
            if anchor not in revised and _normalize_for_match(anchor) not in normalized_revised:
                raise ContentRefineError("invalid_revision", f"{change_id}: anchor not in revised")
            if anchor in used_anchors:
                raise ContentRefineError("invalid_revision", f"{change_id}: duplicate anchor")
            used_anchors.add(anchor)

        validated_changes.append(
            {
                "id": change_id,
                "kind": kind,
                "sources": sources,
                "target": target,
                "anchor": anchor,
                "note": note,
            }
        )

    if ratio > max_change_ratio:
        raise ContentRefineError(
            "change_ratio_exceeded",
            f"ratio={ratio:.2f} max={max_change_ratio:.2f}",
        )

    return {
        "version": 1,
        "granularity": "sentence",
        "changes": validated_changes,
        "stats": {
            "change_ratio": round(ratio, 4),
            "change_count": len(validated_changes),
        },
    }


def refine_content_with_llm(
    db: Session,
    *,
    original_text: str,
    title_hint: str | None,
    preset_id: str,
    llm: LLMBackend | None = None,
) -> ContentRefineResult:
    preset = REFINE_PRESETS.get(preset_id) or REFINE_PRESETS[DEFAULT_REFINE_PRESET]
    try:
        normalized_original = validate_ingest_text(original_text)
    except ValueError as exc:
        raise ContentRefineError(str(exc)) from exc

    user_parts = [
        f"Aufgabe: {preset['instruction']}",
        f"ORIGINAL:\n{normalized_original}",
    ]
    if title_hint and title_hint.strip():
        user_parts.insert(1, f"Vorgeschlagener Titel: {title_hint.strip()}")

    backend = llm or get_llm(db=db)
    try:
        response = backend.chat(
            [
                {"role": "system", "content": REFINE_SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            tools=[],
        )
    except LLMError as exc:
        raise ContentRefineError("llm_failed", str(exc)) from exc

    if not response.content:
        raise ContentRefineError("llm_empty_response")

    parsed = _parse_json_response(response.content)
    title = str(parsed.get("title", "")).strip()
    if not title:
        title = (title_hint or "Wissensbeitrag").strip()[:200]
    if len(title) > 200:
        raise ContentRefineError("invalid_title")

    summary = str(parsed.get("summary", "")).strip()[:2000]
    keywords_raw = parsed.get("keywords") or []
    if isinstance(keywords_raw, str):
        keywords = [part.strip() for part in keywords_raw.split(",") if part.strip()]
    else:
        keywords = [str(item).strip() for item in keywords_raw if str(item).strip()]

    revised = str(parsed.get("content", "")).strip()
    try:
        validate_ingest_text(revised)
    except ValueError as exc:
        raise ContentRefineError(str(exc)) from exc

    revision = validate_revision(
        normalized_original,
        revised,
        {"changes": parsed.get("changes") or []},
    )

    return ContentRefineResult(
        title=title,
        summary=summary,
        keywords=keywords,
        content=revised,
        revision=revision,
    )


def revision_from_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
