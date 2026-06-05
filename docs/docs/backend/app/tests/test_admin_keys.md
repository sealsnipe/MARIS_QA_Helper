# `backend/app/tests/test_admin_keys.py`

**Quellpfad:** `backend/app/tests/test_admin_keys.py`

## Zweck und logischer Aufbau

Tests für Admin-Keys (Secrets-Admin + OAuth-Device-Flow-Integration): Masking, Set/Clear, effective Fallbacks, Integration-Token Enable/Disable, OAuth-Status.

Nutzung von client (admin login), db.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.secrets_admin`, `app.config`, Test-Client + login aus conftest, pytest
- **Wird genutzt von:** pytest
- **HTTP / UI:** GET/PATCH/DELETE /api/admin/keys*, OAuth-Device Endpoints
- **Daten:** app_secrets (test DB), Settings-Overrides via monkey/env

## (Optional) Tests

- Admin-only: non-admin → 403.
- Masking: values >4 chars → ••••last4; short/empty → "".
- Set + get_effective: DB override > .env; clear → back to env or "".
- Integration enabled: Token set → enabled; empty → disabled (503 on v1).
- OAuth device flow stubs (start/poll/refresh via mocks or status).
- Error cases: invalid name → 400.
