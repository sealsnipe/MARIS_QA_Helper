from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx
from openai import OpenAI

from app.config import get_settings


class LLMError(Exception):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    assistant_message: dict[str, Any]


class LLMBackend(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse: ...


def _last_user_message(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content
    return ""


class OpenAILLM:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(str(exc)) from exc

        choice = response.choices[0].message
        tool_calls: list[ToolCall] = []
        if choice.tool_calls:
            for call in choice.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=call.id,
                        name=call.function.name,
                        arguments=args,
                    )
                )

        assistant_message: dict[str, Any] = {"role": "assistant", "content": choice.content}
        if tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in tool_calls
            ]

        return LLMResponse(
            content=choice.content,
            tool_calls=tool_calls,
            assistant_message=assistant_message,
        )


class CodexOAuthLLM:
    """Codex streaming backend; synthesizes an initial tool call when tools are requested."""

    def __init__(self, auth_path: Path, base_url: str, model: str) -> None:
        self._auth_path = auth_path
        self._base_url = base_url.rstrip("/")
        self._model = model

    def _headers(self) -> dict[str, str]:
        try:
            from oauth_codex import Client
            from oauth_codex.store import FileTokenStore
        except ImportError as exc:
            raise LLMError("oauth_codex_missing") from exc

        client = Client(
            token_store=FileTokenStore(path=self._auth_path),
            base_url=self._base_url,
        )
        client.authenticate()
        headers = dict(client.auth.get_headers())
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "text/event-stream"
        return headers

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        has_tool_results = any(message.get("role") == "tool" for message in messages)
        if tools and not has_tool_results:
            query = _last_user_message(messages)
            call_id = f"call_{uuid.uuid4().hex[:12]}"
            tool_call = ToolCall(
                id=call_id,
                name="search_knowledge_base",
                arguments={"query": query},
            )
            return LLMResponse(
                content=None,
                tool_calls=[tool_call],
                assistant_message={
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.arguments),
                            },
                        }
                    ],
                },
            )

        system_parts = [message["content"] for message in messages if message.get("role") == "system"]
        instructions = "\n\n".join(part for part in system_parts if isinstance(part, str))
        input_messages: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role in {"user", "assistant"} and content:
                input_messages.append({"role": role, "content": content})
            elif role == "tool" and content:
                input_messages.append({"role": "user", "content": f"[Tool-Ergebnis]\n{content}"})

        payload = {
            "model": self._model,
            "input": input_messages,
            "instructions": instructions,
            "store": False,
            "stream": True,
        }

        try:
            answer = self._stream_response(payload)
        except Exception as exc:
            raise LLMError(str(exc)) from exc

        return LLMResponse(
            content=answer,
            tool_calls=[],
            assistant_message={"role": "assistant", "content": answer},
        )

    def _stream_response(self, payload: dict[str, Any]) -> str:
        parts: list[str] = []
        with httpx.stream(
            "POST",
            f"{self._base_url}/responses",
            headers=self._headers(),
            json=payload,
            timeout=120.0,
        ) as response:
            if response.status_code >= 400:
                body = response.read().decode(errors="replace")
                raise LLMError(f"{response.status_code} {body[:300]}")

            for line in response.iter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                event = json.loads(line[6:])
                if event.get("type") == "response.output_text.delta":
                    parts.append(event.get("delta") or "")

        answer = "".join(parts).strip()
        if not answer:
            raise LLMError("empty_answer")
        return answer


_llm_backend: LLMBackend | None = None


def get_llm() -> LLMBackend:
    global _llm_backend
    if _llm_backend is None:
        settings = get_settings()
        if settings.uses_chatgpt_oauth:
            auth_path = Path(settings.codex_oauth_auth_path)
            _llm_backend = CodexOAuthLLM(
                auth_path=auth_path,
                base_url=settings.CODEX_BASE_URL,
                model=settings.CHAT_MODEL,
            )
        else:
            _llm_backend = OpenAILLM(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.CHAT_MODEL,
            )
    return _llm_backend


def set_llm(backend: LLMBackend | None) -> None:
    global _llm_backend
    _llm_backend = backend


_vision_transcriber_override: Callable[[bytes, str, str], str] | None = None


def set_vision_transcriber(fn: Callable[[bytes, str, str], str] | None) -> None:
    global _vision_transcriber_override
    _vision_transcriber_override = fn


def _image_data_url(image_data: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _oauth_auth_headers(auth_path: Path, base_url: str, *, accept_json: bool) -> dict[str, str]:
    try:
        from oauth_codex import Client
        from oauth_codex.store import FileTokenStore
    except ImportError as exc:
        raise LLMError("oauth_codex_missing") from exc

    client = Client(
        token_store=FileTokenStore(path=auth_path),
        base_url=base_url.rstrip("/"),
    )
    client.authenticate()
    headers = dict(client.auth.get_headers())
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json" if accept_json else "text/event-stream"
    return headers


def _extract_responses_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in data.get("output") or []:
        if item.get("type") == "message":
            for block in item.get("content") or []:
                block_type = block.get("type")
                if block_type in {"output_text", "text"}:
                    parts.append(block.get("text") or "")
        elif item.get("type") == "output_text":
            parts.append(item.get("text") or "")
    return "".join(parts).strip()


def _transcribe_image_oauth(image_data: bytes, mime_type: str, prompt: str) -> str:
    settings = get_settings()
    auth_path = Path(settings.codex_oauth_auth_path)
    headers = _oauth_auth_headers(auth_path, settings.CODEX_BASE_URL, accept_json=False)
    payload = {
        "model": settings.VISION_MODEL,
        "instructions": prompt,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Bitte das Bild gemäß den Anweisungen verarbeiten."},
                    {
                        "type": "input_image",
                        "image_url": _image_data_url(image_data, mime_type),
                        "detail": "auto",
                    },
                ],
            }
        ],
        "store": False,
        "stream": True,
    }
    parts: list[str] = []
    try:
        with httpx.stream(
            "POST",
            f"{settings.CODEX_BASE_URL.rstrip('/')}/responses",
            headers=headers,
            json=payload,
            timeout=120.0,
        ) as response:
            if response.status_code >= 400:
                body = response.read().decode(errors="replace")
                raise LLMError(f"{response.status_code} {body[:300]}")

            for line in response.iter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                event = json.loads(line[6:])
                if event.get("type") == "response.output_text.delta":
                    parts.append(event.get("delta") or "")
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(str(exc)) from exc

    text = "".join(parts).strip()
    if not text:
        raise LLMError("empty_answer")
    return text


def _transcribe_image_api_key(image_data: bytes, mime_type: str, prompt: str) -> str:
    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
    try:
        response = client.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _image_data_url(image_data, mime_type),
                                "detail": "auto",
                            },
                        },
                    ],
                }
            ],
        )
    except Exception as exc:
        raise LLMError(str(exc)) from exc

    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise LLMError("empty_answer")
    return text


def transcribe_image(image_data: bytes, mime_type: str, *, prompt: str) -> str:
    if _vision_transcriber_override is not None:
        return _vision_transcriber_override(image_data, mime_type, prompt)

    settings = get_settings()
    if settings.uses_chatgpt_oauth:
        return _transcribe_image_oauth(image_data, mime_type, prompt)
    return _transcribe_image_api_key(image_data, mime_type, prompt)
