from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.chunking import validate_ingest_text
from app.content_refine import ContentRefineError, refine_content_with_llm, validate_revision


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
