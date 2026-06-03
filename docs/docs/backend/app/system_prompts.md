# `backend/app/system_prompts.py`

**Quellpfad:** `backend/app/system_prompts.py`

## Zweck und logischer Aufbau

Verwaltet **System-Prompts** in SQLite: globaler Prompt (`customer_id=None`) und optionale kundenspezifische Ergänzungen. Stellt Lesen, Schreiben und Zusammenbau des **effektiven Prompts** für den Agent bereit.

Lesereihenfolge: Konstante `GLOBAL_PROMPT_SCOPE` → Hilfsfunktion `_scope_key` → CRUD/Lese-Funktionen → `get_effective_system_prompt` (Zusammenführung) → `ensure_default_global_prompt` (Bootstrap) → `list_prompt_scopes` (Admin-Liste).

Im Datenfluss: Der Agent ruft `get_effective_system_prompt` mit aktiver Mandanten-ID auf; die Admin-UI (`/admin/prompts`, API `PUT /api/admin/system-prompt`) nutzt `get_system_prompt` / `set_system_prompt`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.customers`: `is_global_customer`
  - `app.models`: `SystemPrompt`, `utc_now_iso`
  - `app.prompts`: `DEFAULT_GLOBAL_SYSTEM_PROMPT`, `GLOBAL_MODE_HINT`, `MARKDOWN_FORMATTING_HINT`
  - `sqlalchemy`: `select`, `Session`
- **Wird genutzt von:**
  - `backend/app/agent.py` — effektiver Prompt vor LLM-Aufruf
  - `backend/app/routes.py` — Admin-API und Seitenkontext
  - Startup/Seed (falls `ensure_default_global_prompt` aufgerufen)
- **HTTP / UI:** `GET/PUT /api/admin/system-prompt`, Template `admin_prompts.html`
- **Daten:** SQLite-Tabelle `SystemPrompt` (PK `scope`)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `GLOBAL_PROMPT_SCOPE` | Konstante (`"__global__"`) | Primärschlüssel-Wert für den globalen Prompt in `SystemPrompt.scope` |

## Funktionen und Klassen

### `_scope_key(customer_id: str | None) -> str`

**Beschreibung:** Mappt `None`/fehlende ID auf `GLOBAL_PROMPT_SCOPE`, sonst Mandanten-ID.

**Parameter / Rückgabe:** Optionale Kunden-ID. Rückgabe: DB-Scope-String.

**Aufrufer / Aufgerufene:** Intern von `get_system_prompt` und `set_system_prompt`.

---

### `get_system_prompt(db: Session, customer_id: str | None) -> str | None`

**Beschreibung:** Liest gespeicherten Prompt für einen Scope; leerer Inhalt → `None`.

**Parameter / Rückgabe:** DB-Session, optional `customer_id` (`None` = global). Rückgabe: getrimmter Text oder `None`.

**Ablauf / lokale Variablen:** `row` — ORM-Zeile per `db.get(SystemPrompt, _scope_key(...))`.

**Aufrufer / Aufgerufene:** `get_effective_system_prompt`, `set_system_prompt`, `ensure_default_global_prompt`, Admin-API.

---

### `get_effective_system_prompt(db: Session, customer_id: str) -> str`

**Beschreibung:** Baut den an den Agent übergebenen Prompt: global + kundenspezifisch (falls nicht Global-Kunde), Fallback auf Default, plus Modus- und Markdown-Hinweise.

**Parameter / Rückgabe:** Session und Mandanten-ID. Rückgabe: zusammengefügter Prompt-String (`"\n\n".join`).

**Ablauf / lokale Variablen:** `parts` — Liste der Prompt-Segmente in Reihenfolge.

**Aufrufer / Aufgerufene:** Agent; nutzt `get_system_prompt`, `DEFAULT_GLOBAL_SYSTEM_PROMPT`, `GLOBAL_MODE_HINT`, `MARKDOWN_FORMATTING_HINT`.

---

### `set_system_prompt(db: Session, customer_id: str | None, content: str, *, updated_by: str) -> SystemPrompt`

**Beschreibung:** Legt Prompt an oder aktualisiert bestehenden Eintrag; committet und refreshed die Zeile.

**Parameter / Rückgabe:** Scope (`customer_id`), Inhalt, Audit-Feld `updated_by`. Rückgabe: `SystemPrompt`-Instanz.

**Ablauf / lokale Variablen:** `key`, `now`, `cleaned` (getrimmter Inhalt).

**Aufrufer / Aufgerufene:** Admin-API `api_put_system_prompt`, `ensure_default_global_prompt`.

---

### `ensure_default_global_prompt(db: Session, updated_by: str = "system") -> None`

**Beschreibung:** Seed-Hilfe: schreibt `DEFAULT_GLOBAL_SYSTEM_PROMPT`, wenn noch kein globaler Prompt existiert.

**Parameter / Rückgabe:** Session, optional Audit-Name. Kein Rückgabewert.

**Aufrufer / Aufgerufene:** Ruft `get_system_prompt` und ggf. `set_system_prompt` auf.

---

### `list_prompt_scopes(db: Session) -> list[SystemPrompt]`

**Beschreibung:** Listet alle gespeicherten Prompt-Scopes sortiert nach `scope` (Admin-Übersicht).

**Parameter / Rückgabe:** Session. Rückgabe: Liste von `SystemPrompt`-ORM-Objekten.

**Aufrufer / Aufgerufene:** Potenziell Admin-Erweiterungen; aktuell im Repo primär Modul-API.
