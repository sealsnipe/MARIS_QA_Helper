# `backend/app/tests/test_chats.py`

**Quellpfad:** `backend/app/tests/test_chats.py`

## Zweck und logischer Aufbau

Integrationstests für **Chat-Sessions** und **Nachrichtenpersistenz**: Anlegen und Auflisten von Chats, Speicherung von User-/Assistant-Nachrichten nach `POST /api/chat` (mit gemocktem Agent), sowie **Mandanten-Isolation** der Chat-Historie.

`test_chat_persists_messages` patcht `app.routes.run_agent`, um den echten Agenten zu umgehen und deterministische Antworten zu liefern.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.agent.ChatResult` (für Mock-Rückgabe)
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
  - `monkeypatch` (nur in `test_chat_persists_messages`)
- **Wird genutzt von:** pytest
- **HTTP / UI:** `POST/GET /api/chats`, `GET /api/chats/{chat_id}`, `POST /api/chat`, `POST /api/session/customer`
- **Daten:** SQLite Chat-/Message-Tabellen (über `app.chats`)
- **Abgedecktes Modul:** `backend/app/chats.py`, `backend/app/routes.py`

## Konstanten, Typen und Modulebene

Keine Modulebenen-Symbole außer Testfunktionen.

## Funktionen und Klassen

### `test_create_and_list_chats(client, db_session)`

**Beschreibung:** `POST /api/chats` erzeugt Chat; `GET /api/chats` enthält die neue `id`.

**Parameter / Rückgabe:** `client`, `db_session`.

**Ablauf / lokale Variablen:** Mandant in Session; `chat_id` aus Create-JSON; `listed` mit Assertion `any(item["id"] == chat_id)`.

**Aufrufer / Aufgerufene:** Chat-API in `routes.py` / `chats.py`.

---

### `test_chat_persists_messages(client, db_session, monkeypatch)`

**Beschreibung:** Nach Chat-Nachricht sind User- und Assistant-Inhalt in `GET /api/chats/{id}` gespeichert.

**Parameter / Rückgabe:** Zusätzlich `monkeypatch`.

**Ablauf / lokale Variablen:** Mock `run_agent` → `ChatResult("Antworttext", [source-dict], False)`; `messages` — zwei Einträge mit Inhalten „Was ist VPN?“ und „Antworttext“.

**Aufrufer / Aufgerufene:** `monkeypatch.setattr("app.routes.run_agent", ...)`.

---

### `test_chat_history_isolated_by_customer(client, db_session)`

**Beschreibung:** Chats eines Mandanten sind für anderen aktiven Mandanten weder listbar noch per ID abrufbar (403).

**Ablauf / lokale Variablen:** `acme_chat_id` unter `bg-ludwigshafen`, `globex_chat_id` unter `kkrr`; `globex_ids` ohne `acme_chat_id`; `forbidden` auf fremde Chat-ID → 403.

**Aufrufer / Aufgerufene:** Mandanten-Scope in `chats.py` / Routes.

## (Optional) Tests

- **Fixtures:** `client`, `db_session`, `monkeypatch` (ein Test); autouse KI-Mocks. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedecktes Modul:** `backend/app/chats.py`, `backend/app/routes.py`, Mock von `backend/app/agent.py` (`ChatResult`).

| Test | Intent |
|---|---|
| `test_create_and_list_chats` | Chat anlegen und listen |
| `test_chat_persists_messages` | User+Assistant-Nachrichten in DB |
| `test_chat_history_isolated_by_customer` | Chats mandantenscharf getrennt |
