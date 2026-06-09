# `backend/app/tests/test_integration_api.py`

**Quellpfad:** `backend/app/tests/test_integration_api.py`

## Zweck und logischer Aufbau

Tests für /api/v1 Integration: Bearer-Token, disabled, ask (scoped agent + chat persist), knowledge-content ingest (batch, idempotent, errors), 403/401 cases.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.integration_*`, `app.knowledge_center`, `app.agent`, conftest (create integration user?), client, monkeypatch settings
- **Wird genutzt von:** pytest
- **HTTP / UI:** /api/v1/ask , /api/v1/knowledge-content (Bearer)
- **Daten:** chat_sessions (integration), knowledge_*, customers

## (Optional) Tests

- No token / bad token → 401 invalid_token.
- integration_enabled=False → 503.
- ask: scoped (no cross-customer), chat_id roundtrip, sources.
- knowledge ingest: created/updated/skipped, external_id dedup, invalid items → errors[].
- Forbidden customer in ask.
- DB-only token (update_secret) funktioniert; nach Rotate im DB ist alter ENV-Token invalid; DB-leer override deaktiviert trotz ENV-Token.
