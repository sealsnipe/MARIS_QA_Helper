# `backend/app/tests/test_health.py`

**Quellpfad:** `backend/app/tests/test_health.py`

## Zweck und logischer Aufbau

Minimaler **Smoke-Test** für den Health-Check-Endpunkt der FastAPI-App. Eine Testfunktion prüft, dass `GET /api/health` ohne Authentifizierung `200` und `{"ok": true}` zurückgibt.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** keine expliziten App-Imports (nur pytest über Discovery)
- **Wird genutzt von:** pytest
- **HTTP / UI:** `GET /api/health`
- **Daten:** keine
- **Abgedecktes Modul:** `backend/app/routes.py` (`GET /api/health`)

## Konstanten, Typen und Modulebene

Keine Modulebenen-Symbole.

## Funktionen und Klassen

### `test_health_endpoint(client)`

**Beschreibung:** Health-Endpunkt antwortet mit OK-Payload.

**Parameter / Rückgabe:** `client` — `TestClient` aus Conftest.

**Ablauf / lokale Variablen:** `response` — Status 200, JSON exakt `{"ok": True}` (Python `True` entspricht JSON `true`).

**Aufrufer / Aufgerufene:** `client.get("/api/health")`.

## (Optional) Tests

- **Fixtures:** `client` (inkl. `db_session`-Kette aus Conftest); autouse KI-Mocks ohne Relevanz.
- **Abgedecktes Modul:** `backend/app/routes.py`.

| Test | Intent |
|---|---|
| `test_health_endpoint` | Liveness `GET /api/health` → 200, `ok: true` |
