from __future__ import annotations

import json
from unittest.mock import patch

from app.llm_catalog import get_catalog, is_valid_provider_model
from app.tests.conftest import create_user, login


def test_llm_catalog_providers():
    catalog = get_catalog()
    ids = {row["id"] for row in catalog["providers"]}
    assert "openai" in ids
    assert "grok" in ids
    assert "claude" in ids
    assert next(p for p in catalog["providers"] if p["id"] == "claude")["enabled"] is False
    assert is_valid_provider_model("grok", "grok-build-0.1")
    assert is_valid_provider_model("grok", "grok-4.3")
    assert not is_valid_provider_model("grok", "composer-2.5")
    assert not is_valid_provider_model("claude", "claude-3")


def test_create_preset_and_binding(client, db_session):
    create_user(db_session, "admin@example.com", "secret123", tuple(), is_admin=True)
    login(client, "admin@example.com", "secret123")

    catalog = client.get("/api/admin/llm-presets/catalog")
    assert catalog.status_code == 200

    created = client.post(
        "/api/admin/llm-presets",
        json={"name": "Grok Dev", "provider": "grok", "model_id": "grok-build-0.1"},
    )
    assert created.status_code == 200
    preset_id = created.json()["preset"]["id"]

    binding = client.patch(
        f"/api/admin/llm-bindings/chat",
        json={"binding_type": "preset", "preset_id": preset_id},
    )
    assert binding.status_code == 200

    status = client.get("/api/admin/keys")
    assert status.status_code == 200
    body = status.json()
    assert "presets" in body and "bindings" in body
    assert any(row["id"] == preset_id for row in body["presets"])
    chat = next(row for row in body["bindings"] if row["slot"] == "chat")
    assert chat["preset_id"] == preset_id


def test_xai_device_flow_start_mock():
    from app.oauth_xai_flow import start_device_flow

    fake = {
        "device_code": "dc",
        "user_code": "ABCD-1234",
        "verification_uri_complete": "https://auth.x.ai/device",
        "interval": 5,
        "expires_in": 600,
    }

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return fake

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResp()

    with patch("app.oauth_xai_flow.httpx.Client", FakeClient):
        info = start_device_flow()
    assert info["user_code"] == "ABCD-1234"
    assert info["device_code"] == "dc"


def test_assignments_status_embedding_masked(client, db_session):
    create_user(db_session, "admin@example.com", "secret123", tuple(), is_admin=True)
    login(client, "admin@example.com", "secret123")

    resp = client.get("/api/admin/keys")
    assert resp.status_code == 200
    assert "embedding" in resp.json()
    assert "test-openai-key" not in str(resp.json())

    patch_resp = client.patch("/api/admin/keys/embedding", json={"api_key": "sk-embed-1234567890"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["embedding"]["api_key_masked"].endswith("7890")
