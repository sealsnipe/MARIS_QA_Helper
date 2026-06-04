from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import LLMBackend, LLMError, get_llm
from app.prompts import DEFAULT_GLOBAL_SYSTEM_PROMPT, NO_CONTEXT_TEXT, SEARCH_TOOL
from app.retrieval import (
    SourceRegistry,
    clamp_top_k,
    filter_sources_by_answer_citations,
    format_hits_for_model,
    search_knowledge_base_scoped,
)
from app.system_prompts import get_effective_system_prompt


class AgentError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class ChatResult:
    answer: str
    sources: list[dict[str, Any]]
    no_context: bool


def run(
    customer_id: str,
    message: str,
    top_k: int | None = None,
    *,
    db: Session | None = None,
    llm: LLMBackend | None = None,
    system_prompt: str | None = None,
    scope_customer_ids: list[str] | None = None,
) -> ChatResult:
    settings = get_settings()
    llm = llm or get_llm(db=db)
    default_top_k = clamp_top_k(top_k, settings.TOP_K_DEFAULT)
    if system_prompt is None:
        system_prompt = get_effective_system_prompt(db, customer_id) if db else DEFAULT_GLOBAL_SYSTEM_PROMPT

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message.strip()},
    ]
    registry = SourceRegistry()
    source_offset = 1

    for _round_index in range(settings.MAX_TOOL_ROUNDS):
        try:
            response = llm.chat(messages, tools=[SEARCH_TOOL])
        except LLMError as exc:
            raise AgentError("llm_failed", detail=str(exc)) from exc

        if response.tool_calls:
            messages.append(response.assistant_message)
            for call in response.tool_calls:
                if call.name != "search_knowledge_base":
                    tool_content = "Unbekanntes Tool."
                else:
                    query = str(call.arguments.get("query", "")).strip() or message.strip()
                    requested_top_k = call.arguments.get("top_k")
                    hits = search_knowledge_base_scoped(
                        customer_id,
                        query,
                        clamp_top_k(requested_top_k, default_top_k),
                        scope_customer_ids=scope_customer_ids,
                    )
                    if hits:
                        registry.register(hits)
                    tool_content = format_hits_for_model(hits, start_index=source_offset)
                    source_offset += len(hits)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": tool_content,
                    }
                )
            continue

        if not registry.has_hits:
            return ChatResult(NO_CONTEXT_TEXT, [], no_context=True)
        content = (response.content or "").strip()
        if not content:
            return ChatResult(NO_CONTEXT_TEXT, [], no_context=True)
        sources = filter_sources_by_answer_citations(registry.ordered_sources(), content)
        return ChatResult(content, sources, no_context=False)

    try:
        final = llm.chat(messages, tools=[])
    except LLMError as exc:
        raise AgentError("llm_failed", detail=str(exc)) from exc

    if not registry.has_hits:
        return ChatResult(NO_CONTEXT_TEXT, [], no_context=True)

    content = (final.content or "").strip()
    if not content:
        return ChatResult(NO_CONTEXT_TEXT, [], no_context=True)
    sources = filter_sources_by_answer_citations(registry.ordered_sources(), content)
    return ChatResult(content, sources, no_context=False)
