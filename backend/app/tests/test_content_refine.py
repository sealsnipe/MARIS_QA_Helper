from __future__ import annotations

import pytest

from app.content_refine import ContentRefineError, validate_revision


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
