"""Mandatory tenant-isolation gates (M7 / docs 10 §3)."""

from __future__ import annotations

from typing import Any

import pytest

from app.agent import run
from app.customers import collection_name
from app.ingestion import ingest_text
from app.llm import LLMResponse, ToolCall, set_llm
from app.retrieval import search_knowledge_base
from app.tests.conftest import create_customer, create_user, login


class _FinalAnswerLLM:
    def __init__(self, scripted: list[LLMResponse]) -> None:
        self.scripted = scripted

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        if not self.scripted:
            raise AssertionError("no scripted responses left")
        return self.scripted.pop(0)


ACME_TEXT = (
    "BG Ludwigshafen VPN Eskalation: FortiGate prüfen, danach Netzwerkteam informieren. "
    "Nur für BG Ludwigshafen-Mandanten sichtbar."
)
GLOBEX_TEXT = (
    "KKRR Firewall FAQ: Port 443 freischalten, dann Proxy-Logs prüfen. "
    "Nur für KKRR-Mandanten sichtbar."
)


def test_ingestion_uses_separate_collections_per_customer(
    db_session, fake_vector_store, fake_embeddings
):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")

    ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="BG Ludwigshafen VPN",
        text=ACME_TEXT,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )
    ingest_text(
        db_session,
        customer_id="kkrr",
        title="KKRR Firewall",
        text=GLOBEX_TEXT,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    acme_bucket = fake_vector_store.collections[collection_name("bg-ludwigshafen")]
    globex_bucket = fake_vector_store.collections[collection_name("kkrr")]
    assert acme_bucket
    assert globex_bucket
    assert acme_bucket.keys().isdisjoint(globex_bucket.keys())

    acme_titles = {payload[1].get("title") for payload in acme_bucket.values()}
    globex_titles = {payload[1].get("title") for payload in globex_bucket.values()}
    assert acme_titles == {"BG Ludwigshafen VPN"}
    assert globex_titles == {"KKRR Firewall"}


def test_search_and_agent_scoped_to_active_customer(db_session, fake_vector_store, fake_embeddings):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")

    ingest_text(
        db_session,
        customer_id="bg-ludwigshafen",
        title="BG Ludwigshafen VPN",
        text=ACME_TEXT,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )
    ingest_text(
        db_session,
        customer_id="kkrr",
        title="KKRR Firewall",
        text=GLOBEX_TEXT,
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
    )

    globex_hits = search_knowledge_base(
        "kkrr",
        "VPN Firewall",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
        min_score=0.0,
    )
    assert globex_hits
    assert all("KKRR" in hit.title or "KKRR" in hit.text for hit in globex_hits)
    assert all("BG Ludwigshafen" not in hit.title for hit in globex_hits)

    acme_hits = search_knowledge_base(
        "bg-ludwigshafen",
        "VPN Firewall",
        embeddings=fake_embeddings,
        vector_store=fake_vector_store,
        min_score=0.0,
    )
    assert acme_hits
    assert all("BG Ludwigshafen" in hit.title or "BG Ludwigshafen" in hit.text for hit in acme_hits)

    llm = _FinalAnswerLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall("call_1", "search_knowledge_base", {"query": "VPN"})],
                assistant_message={"role": "assistant", "tool_calls": []},
            ),
            LLMResponse(
                content="KKRR Antwort [1].",
                tool_calls=[],
                assistant_message={"role": "assistant", "content": "KKRR Antwort [1]."},
            ),
        ]
    )
    set_llm(llm)
    try:
        result = run("kkrr", "VPN Problem?", db=db_session)
    finally:
        set_llm(None)

    assert result.no_context is False
    assert result.sources
    assert result.sources[0]["title"] == "KKRR Firewall"
    assert all(source["title"] != "BG Ludwigshafen VPN" for source in result.sources)


def test_documents_api_lists_only_active_customer(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "sven@example.com", "secret123", ("bg-ludwigshafen", "kkrr"))
    login(client, "sven@example.com", "secret123")

    client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})
    create = client.post(
        "/api/documents/text",
        json={"title": "BG Ludwigshafen Doc", "text": ACME_TEXT},
    )
    assert create.status_code == 200

    acme_list = client.get("/api/documents")
    assert acme_list.status_code == 200
    assert len(acme_list.json()["documents"]) == 1
    assert acme_list.json()["documents"][0]["title"] == "BG Ludwigshafen Doc"

    client.post("/api/session/customer", json={"customer_id": "kkrr"})
    globex_list = client.get("/api/documents")
    assert globex_list.status_code == 200
    assert globex_list.json()["documents"] == []


def test_forbidden_customer_returns_403_on_scoped_operations(client, db_session):
    create_customer(db_session, "bg-ludwigshafen", "BG Ludwigshafen")
    create_customer(db_session, "kkrr", "Katholische Kliniken Rhein Ruhr")
    create_user(db_session, "anna@example.com", "secret123", ("kkrr",))
    login(client, "anna@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "kkrr"})

    switch = client.post("/api/session/customer", json={"customer_id": "bg-ludwigshafen"})
    assert switch.status_code == 403
    assert switch.json() == {"error": "forbidden_customer"}

    assert client.get("/api/customers").json()["active"] == "kkrr"

    set_llm(
        _FinalAnswerLLM(
            [LLMResponse(content="Hallo", tool_calls=[], assistant_message={"role": "assistant", "content": "Hallo"})]
        )
    )
    chat = client.post("/api/chat", json={"message": "Hallo"})
    assert chat.status_code == 200


@pytest.mark.parametrize(
    "invalid_slug",
    ["BG Ludwigshafen", "../bad-slug", "bad/b", "bad b", ""],
)
def test_collection_name_rejects_invalid_slugs(invalid_slug):
    with pytest.raises(ValueError, match="invalid customer slug"):
        collection_name(invalid_slug)
