from __future__ import annotations

from typing import Any, Literal

ProviderId = Literal["openai", "grok", "claude", "gemini"]

PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI (ChatGPT OAuth)",
    "grok": "Grok (xAI OAuth)",
    "claude": "Claude",
    "gemini": "Gemini",
}

PROVIDER_ENABLED: dict[str, bool] = {
    "openai": True,
    "grok": True,
    "claude": False,
    "gemini": False,
}

# OAuth-capable models per provider (platform API models like gpt-4o are excluded).
OAUTH_MODELS: dict[str, list[dict[str, str]]] = {
    "openai": [
        {"id": "gpt-5.4-mini", "label": "GPT 5.4 Mini"},
        {"id": "gpt-5.5", "label": "GPT 5.5"},
    ],
    "grok": [
        {"id": "grok-build-0.1", "label": "Grok Build 0.1"},
        {"id": "grok-4.3", "label": "Grok 4.3"},
    ],
}

# Composer 2.5 is only exposed in the Grok Build CLI (/model menu), not on api.x.ai.
COMPOSER_CLI_ONLY_NOTE = (
    "Composer 2.5 ist derzeit nur in der Grok-Build-CLI verfügbar, "
    "nicht als öffentlicher API-Slug über OAuth."
)

LLM_SLOTS: list[dict[str, Any]] = [
    {"id": "chat", "label": "Chat (Agent)", "description": "Haupt-LLM für Support-Chat und Agent."},
    {
        "id": "vision",
        "label": "Vision / Bild-zu-Text",
        "description": "Bildanalyse. Standard: dasselbe Preset wie Chat.",
        "allow_inherit": True,
    },
    {
        "id": "similarity",
        "label": "Similarity Agent",
        "description": "LLM-Vorschläge beim Dokument-Merge.",
        "allow_inherit": True,
    },
    {
        "id": "kc_refine",
        "label": "KC Content Refine",
        "description": "KI-Überarbeitung bei Wissensbeiträgen.",
        "allow_inherit": True,
    },
]


def get_catalog() -> dict[str, Any]:
    providers = []
    for pid, label in PROVIDER_LABELS.items():
        providers.append(
            {
                "id": pid,
                "label": label,
                "enabled": PROVIDER_ENABLED.get(pid, False),
                "models": OAUTH_MODELS.get(pid, []) if PROVIDER_ENABLED.get(pid) else [],
            }
        )
    return {"providers": providers, "slots": LLM_SLOTS, "notes": {"composer_cli_only": COMPOSER_CLI_ONLY_NOTE}}


def is_valid_provider_model(provider: str, model_id: str) -> bool:
    if not PROVIDER_ENABLED.get(provider):
        return False
    return any(row["id"] == model_id for row in OAUTH_MODELS.get(provider, []))
