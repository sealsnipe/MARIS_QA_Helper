from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.chunking import validate_ingest_text
from app.content_refine import ContentRefineError, refine_content_with_llm, refine_pipeline_with_llm, validate_revision


def test_validate_revision_accepts_split_change():
    original = "Der VPN bricht ab wenn das WLAN wechselt."
    revised = "Der VPN bricht ab, wenn das WLAN wechselt.\nNeu verbinden ist nötig."
    revision = validate_revision(
        original,
        revised,
        {
            "changes": [
                {
                    "id": "c1",
                    "kind": "split",
                    "sources": [original],
                    "target": revised,
                    "anchor": "Der VPN bricht ab, wenn das WLAN wechselt.",
                }
            ]
        },
    )
    assert revision["changes"][0]["kind"] == "split"


def test_validate_revision_rejects_missing_source():
    with pytest.raises(ContentRefineError) as exc:
        validate_revision(
            "Originaltext mit genug Zeichen.",
            "Geänderter Text mit genug Zeichen.",
            {
                "changes": [
                    {
                        "id": "c1",
                        "kind": "replace",
                        "sources": ["existiert nicht"],
                        "target": "Geänderter Text mit genug Zeichen.",
                        "anchor": "Geänderter",
                    }
                ]
            },
        )
    assert exc.value.code == "invalid_revision"


def test_refine_stores_normalized_content(db_session):
    original = "VPN bricht ab   wenn WLAN wechselt — kurz notiert."
    revised_raw = "VPN bricht ab, wenn das WLAN wechselt. Neu verbinden ist nötig."
    llm = MagicMock()
    llm.chat.return_value = MagicMock(
        content=json.dumps(
            {
                "title": "VPN Problem",
                "summary": "Kurznotiz ausformuliert.",
                "keywords": ["vpn"],
                "content": f"  {revised_raw}  ",
                "changes": [
                    {
                        "id": "c1",
                        "kind": "replace",
                        "sources": [original.strip()],
                        "target": revised_raw,
                        "anchor": "VPN bricht ab, wenn das WLAN wechselt.",
                    }
                ],
            }
        )
    )

    result = refine_content_with_llm(
        db_session,
        original_text=original,
        title_hint=None,
        preset_id="expand_notes",
        llm=llm,
    )

    assert result.content == validate_ingest_text(revised_raw)
    assert result.content == result.content.strip()
    assert result.revision["version"] == 2
    assert result.revision["stats"]["step_count"] == 1


def test_pipeline_runs_steps_in_order(db_session):
    from app.content_refine import refine_pipeline_with_llm, validate_preset_ids

    original = "Der VPN bricht ab wenn das WLAN wechselt und muss neu verbunden werden."
    step1_out = "Der VPN bricht ab, wenn das WLAN wechselt und muss neu verbunden werden."
    step2_out = "Der VPN bricht ab, wenn das WLAN wechselt.\nNeu verbinden ist nötig."

    llm = MagicMock()
    llm.chat.side_effect = [
        MagicMock(
            content=json.dumps(
                {
                    "title": "VPN",
                    "summary": "s1",
                    "keywords": [],
                    "content": step1_out,
                    "changes": [
                        {
                            "id": "c1",
                            "kind": "replace",
                            "sources": [original],
                            "target": step1_out,
                            "anchor": "VPN bricht ab",
                        }
                    ],
                }
            )
        ),
        MagicMock(
            content=json.dumps(
                {
                    "title": "VPN Guide",
                    "summary": "s2",
                    "keywords": ["vpn"],
                    "content": step2_out,
                    "changes": [
                        {
                            "id": "c1",
                            "kind": "split",
                            "sources": [step1_out],
                            "target": step2_out,
                            "anchor": "VPN bricht ab, wenn das WLAN wechselt.",
                        }
                    ],
                }
            )
        ),
    ]

    result = refine_pipeline_with_llm(
        db_session,
        original_text=original,
        title_hint=None,
        preset_ids=["expand_notes", "structure"],
        llm=llm,
    )

    assert llm.chat.call_count == 2
    assert result.revision["version"] == 2
    assert result.revision["stats"]["step_count"] == 2
    assert result.revision["pipeline"][0]["input_content"] == validate_ingest_text(original)
    assert result.revision["pipeline"][1]["input_content"] == validate_ingest_text(step1_out)
    assert result.content == validate_ingest_text(step2_out)


def test_validate_preset_ids_rejects_empty():
    from app.content_refine import validate_preset_ids

    with pytest.raises(ContentRefineError) as exc:
        validate_preset_ids([])
    assert exc.value.code == "invalid_presets"


def test_validate_preset_ids_rejects_unknown():
    from app.content_refine import validate_preset_ids

    with pytest.raises(ContentRefineError) as exc:
        validate_preset_ids(["not-a-preset"])
    assert exc.value.code == "invalid_presets"
