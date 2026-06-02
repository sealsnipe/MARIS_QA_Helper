from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.agent import run
from app.llm import LLMResponse, ToolCall, set_llm
from app.prompts import NO_CONTEXT_TEXT
from app.retrieval import RetrievalHit
from app.tests.conftest import create_customer, create_user, login


@dataclass
class FakeLLM:
    scripted: list[LLMResponse]

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        if not self.scripted:
            raise AssertionError("no scripted responses left")
        return self.scripted.pop(0)


def test_agent_no_context_without_hits(client, db_session, monkeypatch):
    create_customer(db_session, "acme", "Acme GmbH")
    create_user(db_session, "sven@example.com", "secret123", ("acme",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "acme"})

    llm = FakeLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall("call_1", "search_knowledge_base", {"query": "VPN"})],
                assistant_message={"role": "assistant", "tool_calls": []},
            ),
            LLMResponse(content="Antwort", tool_calls=[], assistant_message={"role": "assistant", "content": "Antwort"}),
        ]
    )
    set_llm(llm)

    def fake_search(customer_id, query, top_k=None, **kwargs):
        assert customer_id == "acme"
        return []

    monkeypatch.setattr("app.agent.search_knowledge_base_scoped", fake_search)

    response = client.post("/api/chat", json={"message": "Wie geht VPN?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["no_context"] is True
    assert payload["answer"] == NO_CONTEXT_TEXT
    assert payload["sources"] == []
    set_llm(None)


def test_agent_returns_sources_when_hits(client, db_session, monkeypatch):
    create_customer(db_session, "acme", "Acme GmbH")
    create_user(db_session, "sven@example.com", "secret123", ("acme",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "acme"})

    llm = FakeLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall("call_1", "search_knowledge_base", {"query": "VPN"})],
                assistant_message={"role": "assistant", "tool_calls": []},
            ),
            LLMResponse(
                content="Nutze FortiGate [1].",
                tool_calls=[],
                assistant_message={"role": "assistant", "content": "Nutze FortiGate [1]."},
            ),
        ]
    )
    set_llm(llm)

    hit = RetrievalHit(
        document_id="doc-1",
        title="VPN Runbook",
        chunk_index=0,
        text="Prüfe FortiGate zuerst.",
        score=0.9,
    )

    monkeypatch.setattr("app.agent.search_knowledge_base_scoped", lambda *args, **kwargs: [hit])

    response = client.post("/api/chat", json={"message": "VPN Problem?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["no_context"] is False
    assert payload["sources"][0]["title"] == "VPN Runbook"
    assert len(payload["sources"]) == 1
    assert "FortiGate" in payload["answer"]
    set_llm(None)


def test_agent_only_returns_cited_sources(client, db_session, monkeypatch):
    create_customer(db_session, "acme", "Acme GmbH")
    create_user(db_session, "sven@example.com", "secret123", ("acme",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "acme"})

    llm = FakeLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall("call_1", "search_knowledge_base", {"query": "Öffnungszeiten"})],
                assistant_message={"role": "assistant", "tool_calls": []},
            ),
            LLMResponse(
                content="Mo–Fr 8–17 Uhr laut [2].",
                tool_calls=[],
                assistant_message={"role": "assistant", "content": "Mo–Fr 8–17 Uhr laut [2]."},
            ),
        ]
    )
    set_llm(llm)

    hits = [
        RetrievalHit("doc-1", "Allgemein", 0, "Text A", 0.95),
        RetrievalHit("doc-2", "Öffnungszeiten", 1, "Mo–Fr 8–17", 0.88),
        RetrievalHit("doc-3", "Support", 2, "Text C", 0.8),
    ]
    monkeypatch.setattr("app.agent.search_knowledge_base_scoped", lambda *args, **kwargs: hits)

    response = client.post("/api/chat", json={"message": "Öffnungszeiten?"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["n"] == 2
    assert payload["sources"][0]["title"] == "Öffnungszeiten"
    set_llm(None)


def test_chat_requires_customer(client, db_session):
    create_customer(db_session, "acme", "Acme GmbH")
    create_customer(db_session, "globex", "Globex AG")
    create_user(db_session, "sven@example.com", "secret123", ("acme", "globex"))
    login(client, "sven@example.com", "secret123")

    response = client.post("/api/chat", json={"message": "Hallo"})
    assert response.status_code == 403


def test_chat_empty_message(client, db_session):
    create_customer(db_session, "acme", "Acme GmbH")
    create_user(db_session, "sven@example.com", "secret123", ("acme",))
    login(client, "sven@example.com", "secret123")
    client.post("/api/session/customer", json={"customer_id": "acme"})

    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400
    assert response.json()["error"] == "empty_message"
