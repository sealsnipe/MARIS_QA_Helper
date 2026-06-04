from __future__ import annotations

import json
import math

import pytest

from app.document_merge import (
    MergeError,
    apply_document_merge,
    build_merge_preview,
    compose_merged_text,
    cosine_similarity,
    evaluate_merge_confidence,
    finalize_merge_preview,
    llm_suggest_merge,
    merge_preview_for_documents,
    validate_merge_text,
)
from app.ingestion import ingest_text
from app.llm import LLMResponse
from app.models import Document
from app.tests.conftest import create_customer, create_user, login


class TextHashEmbeddings:
    """Deterministic vectors so identical/near-identical blocks align in tests."""

    def _vector(self, text: str) -> list[float]:
        values = [0.0] * 1536
        for index, char in enumerate(text[:400]):
            slot = index % 1536
            values[slot] += (ord(char) % 97) / 100.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_cosine_similarity_identical_vectors() -> None:
    vector = [1.0, 0.0, 0.0]
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_build_merge_preview_detects_modified_added_and_removed() -> None:
    old_text = (
        "Einleitung mit genug Zeichen fuer den Merge-Test und Kontext.\n\n"
        "Der Verguetungsabschnitt beschreibt Regeln fuer Nachtarbeit und Wochenendzuschlaege ausfuehrlich.\n\n"
        "Veralteter Schlussabschnitt wird entfernt und ist nicht mehr gueltig."
    )
    new_text = (
        "Einleitung mit genug Zeichen fuer den Merge-Test und Kontext.\n\n"
        "Der Verguetungsabschnitt beschreibt Regeln fuer Nachtarbeit und Wochenendzuschlaege ab 2026 ausfuehrlich.\n\n"
        "Neuer Anhang zur Dokumentation ab 2026 mit weiteren Hinweisen fuer Teams."
    )
    preview = build_merge_preview(old_text, new_text, embeddings=TextHashEmbeddings())
    kinds = {block["kind"] for block in preview["blocks"]}
    assert "unchanged" in kinds
    assert "modified" in kinds
    assert "added" in kinds
    assert "removed" in kinds
    assert preview["stats"]["modified"] >= 1
    assert preview["stats"]["added"] >= 1
    assert preview["stats"]["removed"] >= 1
    assert len(preview["merged_preview"]) >= 20


def test_compose_merged_text_respects_selections() -> None:
    blocks = [
        {"id": "b0", "kind": "unchanged", "old_text": "Bleibt.", "include": None},
        {"id": "b1", "kind": "modified", "old_text": "Alt.", "new_text": "Neu.", "include": True},
        {"id": "b2", "kind": "removed", "old_text": "Weg.", "include": True},
    ]
    merged = compose_merged_text(blocks, {"b1": True, "b2": True})
    assert "Bleibt." in merged
    assert "Neu." in merged
    assert "Weg." not in merged


def test_merge_preview_for_documents_loads_target(db_session, fake_vector_store) -> None:
    create_customer(db_session, "acme", "Acme")
    base = (
        "Bestehender Wissensinhalt mit ausreichend Zeichen fuer den Document Merge Preview Test."
    )
    ingest_text(
        db_session,
        customer_id="acme",
        title="Handbuch v1",
        text=base,
        embeddings=TextHashEmbeddings(),
        vector_store=fake_vector_store,
    )
    document = db_session.query(Document).one()
    revised = base + "\n\nNeuer Absatz zur Ergaenzung ab naechstem Quartal."
    preview = merge_preview_for_documents(
        db_session,
        "acme",
        document.id,
        revised,
        embeddings=TextHashEmbeddings(),
    )
    assert preview["target_title"] == "Handbuch v1"
    assert preview["target_document_id"] == document.id
    assert any(block["kind"] == "added" for block in preview["blocks"])


def test_apply_document_merge_updates_existing_document(db_session, fake_vector_store) -> None:
    create_customer(db_session, "acme", "Acme")
    base = (
        "Bestehender Wissensinhalt mit ausreichend Zeichen fuer den Document Merge Apply Test."
    )
    ingest_text(
        db_session,
        customer_id="acme",
        title="Handbuch v1",
        text=base,
        embeddings=TextHashEmbeddings(),
        vector_store=fake_vector_store,
    )
    document = db_session.query(Document).one()
    revised = (
        base
        + "\n\n"
        + "Zusatzinformation zur aktualisierten Regelung mit genug Zeichen fuer den Merge."
    )
    preview = build_merge_preview(base, revised, embeddings=TextHashEmbeddings())
    selections = [
        {"id": block["id"], "include": block.get("include")}
        for block in preview["blocks"]
    ]
    result = apply_document_merge(
        db_session,
        "acme",
        document.id,
        revised,
        selections,
        embeddings=TextHashEmbeddings(),
        vector_store=fake_vector_store,
    )
    assert "Zusatzinformation" in result["merged_text"]
    assert result["document"].source_text is not None
    assert "Zusatzinformation" in result["document"].source_text


def test_merge_preview_api(client, db_session, fake_vector_store) -> None:
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})

    base = b"Bestehender API Merge Inhalt mit genug Zeichen fuer die Vorschau."
    first = client.post(
        "/api/documents",
        files={"file": ("base.txt", base, "text/plain")},
    )
    assert first.status_code == 200
    document_id = first.json()["document"]["id"]

    revised = (
        base.decode("utf-8")
        + "\n\nNeuer API-Absatz mit genug Inhalt fuer den Merge-Endpunkt."
    )
    preview = client.post(
        "/api/documents/merge-preview",
        data={"target_document_id": document_id, "text": revised},
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["target_document_id"] == document_id
    assert payload["blocks"]
    assert payload["merged_preview"]

    selections = [{"id": block["id"], "include": block.get("include")} for block in payload["blocks"]]
    merged = client.post(
        f"/api/documents/{document_id}/merge",
        data={"text": revised, "blocks": json.dumps(selections)},
    )
    assert merged.status_code == 200
    assert merged.json()["stats"]


def test_evaluate_merge_confidence_flags_uncertain_structure() -> None:
    preview = finalize_merge_preview(
        {
            "blocks": [],
            "stats": {"unchanged": 0, "modified": 1, "added": 2, "removed": 2},
            "old_block_count": 4,
            "new_block_count": 3,
            "matched_old_blocks": 1,
            "source": "heuristic",
        }
    )
    assert preview["confidence"] < 0.65
    assert preview["needs_llm_assist"] is True
    assert "unsicher" in preview["guidance"].lower() or "ki" in preview["guidance"].lower()


def test_llm_suggest_merge_parses_structured_response() -> None:
    old_text = (
        "Bestehender Wissensinhalt mit ausreichend Zeichen fuer den LLM Merge Test."
    )
    new_text = (
        old_text
        + "\n\n"
        + "Neuer Absatz aus dem Update mit genug Zeichen fuer den LLM Merge Test."
    )

    class FakeMergeLLM:
        def chat(self, messages, tools=None):
            return LLMResponse(
                content=json.dumps(
                    {
                        "summary": "Ein neuer Absatz wurde ergänzt.",
                        "blocks": [
                            {
                                "kind": "unchanged",
                                "old_text": old_text,
                                "new_text": old_text,
                                "include": True,
                                "hint": "Unverändert",
                            },
                            {
                                "kind": "added",
                                "old_text": None,
                                "new_text": "Neuer Absatz aus dem Update mit genug Zeichen fuer den LLM Merge Test.",
                                "include": True,
                                "hint": "Neu hinzufügen",
                            },
                        ],
                    }
                ),
                tool_calls=[],
                assistant_message={"role": "assistant"},
            )

    preview = llm_suggest_merge(old_text, new_text, llm=FakeMergeLLM())
    assert preview["source"] == "llm"
    assert preview["llm_summary"] == "Ein neuer Absatz wurde ergänzt."
    assert preview["stats"]["added"] == 1
    assert "Neuer Absatz" in preview["merged_preview"]
    assert preview["needs_llm_assist"] is False


def test_apply_document_merge_accepts_merged_text_override(db_session, fake_vector_store) -> None:
    create_customer(db_session, "acme", "Acme")
    base = "Bestehender Wissensinhalt mit ausreichend Zeichen fuer den Override Merge Test."
    ingest_text(
        db_session,
        customer_id="acme",
        title="Handbuch v1",
        text=base,
        embeddings=TextHashEmbeddings(),
        vector_store=fake_vector_store,
    )
    document = db_session.query(Document).one()
    override = base + "\n\nManuell angepasster finaler Text mit genug Zeichen fuer den Override."
    result = apply_document_merge(
        db_session,
        "acme",
        document.id,
        base,
        [{"id": "b0", "kind": "unchanged", "old_text": base, "include": None}],
        merged_text_override=override,
        embeddings=TextHashEmbeddings(),
        vector_store=fake_vector_store,
    )
    assert "Manuell angepasster" in result["merged_text"]
    assert "Manuell angepasster" in result["document"].source_text


def test_validate_merge_text_rejects_short_override() -> None:
    with pytest.raises(MergeError) as exc:
        validate_merge_text("zu kurz")
    assert exc.value.code == "empty_text"
