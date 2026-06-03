# `backend/app/chats.py`

**Quellpfad:** `backend/app/chats.py`

## Zweck und logischer Aufbau

Persistenz und Serialisierung von Chat-Sessions und -Nachrichten pro Benutzer und Mandant. Sessions haben Titel und Zeitstempel; Nachrichten speichern Rolle, Inhalt, optional serialisierte Quellen (`sources_json`) und `no_context`-Flag. Assistant-Quellen werden beim Lesen erneut durch Zitationsfilter bereinigt.

Lesereihenfolge: Exception-Klassen → Hilfsfunktion `_truncate_title` → Session-CRUD → Nachrichten-CRUD und Dict-Konverter. Im UI-Flow legt `routes.py` bei Bedarf Sessions an, speichert User-/Assistant-Nachrichten und listet Verläufe.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `json`, `uuid`
  - `app.models.ChatMessage`, `ChatSession`, `utc_now_iso`
  - `app.retrieval.filter_sources_by_answer_citations`
  - `sqlalchemy` (`select`, `Session`)
- **Wird genutzt von:**
  - `backend/app/routes.py` — Chat-API und HTML-Chat
  - `backend/app/main.py` — `ChatNotFoundError`, `ChatForbiddenError` Handler
  - `backend/app/tests/test_chats.py` — indirekt via `ChatResult` aus `agent`
- **HTTP / UI:** Chat-Endpunkte in `routes.py` (Session-Liste, Nachrichten, POST Chat, DELETE)
- **Daten:** SQLite-Tabellen `chat_sessions`, `chat_messages`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ChatNotFoundError` | Exception | Session-ID existiert nicht |
| `ChatForbiddenError` | Exception | Session gehört anderem User/Mandanten |

## Funktionen und Klassen

### `_truncate_title(text: str, limit: int = 72) -> str`

**Beschreibung:** Leitet Session-Titel aus erster User-Nachricht ab (Whitespace normalisiert, gekürzt mit „…").

**Parameter / Rückgabe:** Rohtext und Limit → Titel-String; leer → `"Neuer Chat"`.

**Aufrufer / Aufgerufene:** Nur von `add_message` bei erster User-Nachricht.

---

### `create_session(db, user_id, customer_id, *, title="Neuer Chat") -> ChatSession`

**Beschreibung:** Legt neue Chat-Session mit UUID an und committet.

**Parameter / Rückgabe:** User- und Mandanten-ID, optionaler Titel → `ChatSession`.

**Ablauf / lokale Variablen:** `now` — ISO-Zeitstempel für `created_at`/`updated_at`.

**Aufrufer / Aufgerufene:** ORM `ChatSession`; Aufrufer: `routes.py`.

---

### `get_session_for_user(db, chat_id, user_id, customer_id) -> ChatSession`

**Beschreibung:** Lädt Session mit Mandanten-/User-Isolation; wirft bei Verletzung.

**Parameter / Rückgabe:** IDs → `ChatSession` oder Exception.

**Aufrufer / Aufgerufene:** Aufrufer: `routes.py`, `delete_session`.

---

### `list_sessions(db, user_id, customer_id) -> list[ChatSession]`

**Beschreibung:** Alle Sessions eines Users für einen Mandanten, neueste zuerst (`updated_at desc`).

**Aufrufer / Aufgerufene:** Aufrufer: `routes.py`.

---

### `session_to_dict(session: ChatSession) -> dict[str, Any]`

**Beschreibung:** JSON-taugliche Session-Repräsentation für API/UI.

**Aufrufer / Aufgerufene:** Aufrufer: `routes.py`.

---

### `list_messages(db, chat_id) -> list[dict[str, Any]]`

**Beschreibung:** Chronologische Nachrichtenliste einer Session als Dicts.

**Aufrufer / Aufgerufene:** Ruft `message_to_dict` pro Zeile auf; Aufrufer: `routes.py`.

---

### `message_to_dict(message: ChatMessage) -> dict[str, Any]`

**Beschreibung:** Deserialisiert Nachricht inkl. Quellen aus `sources_json`.

**Ablauf / lokale Variablen:**
- `sources` — aus JSON; bei Assistant mit Inhalt erneut `filter_sources_by_answer_citations`

**Aufrufer / Aufgerufene:** Aufrufer: `list_messages`, indirekt API.

---

### `add_message(db, session, role, content, *, sources=None, no_context=False) -> ChatMessage`

**Beschreibung:** Fügt Nachricht hinzu, aktualisiert Session-`updated_at`, setzt bei erster User-Nachricht Titel.

**Parameter / Rückgabe:** Session, Rolle, Inhalt, optionale Quellen → `ChatMessage`.

**Ablauf / lokale Variablen:**
- `sources_json` — nur für `role=="assistant"` als JSON
- `no_context` — als Integer-Flag in DB

**Aufrufer / Aufgerufene:** Aufrufer: `routes.py` nach Agent-Lauf.

---

### `delete_session(db, chat_id, user_id, customer_id) -> bool`

**Beschreibung:** Löscht Session nach Zugriffsprüfung (Cascade auf Messages via ORM).

**Aufrufer / Aufgerufene:** Ruft `get_session_for_user`; Aufrufer: `routes.py`.
