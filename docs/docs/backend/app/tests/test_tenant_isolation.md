# `backend/app/tests/test_tenant_isolation.py`

**Quellpfad:** `backend/app/tests/test_tenant_isolation.py`

## Zweck und logischer Aufbau

Pflicht-Gates für **Mandantenisolation** (Planungsbezug M7 / docs 10 §3): getrennte Qdrant-Collections pro `customer_id`, mandantenscharfe Suche und Agent-Lauf, dokumentenscharfe HTTP-API und 403 bei verbotenem Mandantenwechsel, plus Validierung von `collection_name` für ungültige Slugs.

Die Datei kombiniert direkte Ingestion/Retrieval/Agent-Tests (ohne HTTP) mit FastAPI-Integrationstests (`client`). Modul-Docstring: „Mandatory tenant-isolation gates“.

Lesereihenfolge: Imports und Hilfs-LLM → Konstanten `ACME_TEXT`/`GLOBEX_TEXT` → Ingestion/Vector-Store-Test → Search/Agent-Test → Documents-API-Test → Forbidden-Customer-Test → parametrisierter Slug-Test.

## Abhängigkeiten und Traces

- **Importiert / nutzt:**
  - `app.agent.run`
  - `app.customers.collection_name`
  - `app.ingestion.ingest_text`
  - `app.llm.LLMResponse`, `ToolCall`, `set_llm`
  - `app.retrieval.search_knowledge_base`
  - `app.tests.conftest`: `create_customer`, `create_user`, `login`
  - `pytest`
- **Wird genutzt von:** pytest (M7-Regression)
- **HTTP / UI:**
  - `POST /api/session/customer`, `POST /api/documents/text`, `GET /api/documents`
  - `GET /api/customers`, `POST /api/chat`
- **Daten:** SQLite `Customer`, `User`, `UserCustomer`, `Document`; Qdrant `InMemoryVectorStore` mit Collections `kb_{customer_id}`
- **Abgedeckte Module:** `ingestion.py`, `retrieval.py`, `agent.py`, `customers.py`, `routes.py` (Session/Dokumente/Chat)

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ACME_TEXT` | `str` | Langer VPN-Eskalationstext für Mandant `bg-ludwigshafen` |
| `GLOBEX_TEXT` | `str` | Firewall-FAQ-Text für Mandant `kkrr` |

## Funktionen und Klassen

### Klasse `_FinalAnswerLLM`

**Beschreibung:** Test-Double für `app.llm`: liefert vorprogrammierte `LLMResponse`-Objekte aus einer Queue (`scripted`).

**Klassenattribute:**

| Name | Art | Beschreibung |
|---|---|---|
| `scripted` | `list[LLMResponse]` | Noch auszuliefernde Antworten (wird per `pop(0)` verbraucht) |

#### `__init__(self, scripted: list[LLMResponse]) -> None`

Speichert die Antwortliste in `self.scripted`.

#### `chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse`

**Beschreibung:** Gibt nächste scripted Antwort zurück; leere Queue → `AssertionError("no scripted responses left")`.

**Parameter / Rückgabe:** `messages`, `tools` werden ignoriert; Rückgabe: `LLMResponse`.

**Aufrufer / Aufgerufene:** Von `app.agent.run` über `set_llm(llm)` injiziert.

---

### `test_ingestion_uses_separate_collections_per_customer(db_session, fake_vector_store, fake_embeddings)`

**Beschreibung:** Zwei Mandanten ingestieren getrennt; Vector-Store-Buckets haben disjunkte Keys und korrekte Titel.

**Parameter / Rückgabe:** Conftest-Session und KI-Mocks.

**Ablauf / lokale Variablen:**
- `acme_bucket` / `globex_bucket` — `fake_vector_store.collections[collection_name(...)]`
- `acme_titles` / `globex_titles` — aus Payload `title` in Bucket-Werten
- Assertions: beide Buckets existieren, Keys disjunkt, Titel je Mandant eindeutig

**Aufrufer / Aufgerufene:** `ingest_text`, `collection_name`.

---

### `test_search_and_agent_scoped_to_active_customer(db_session, fake_vector_store, fake_embeddings)`

**Beschreibung:** `search_knowledge_base` liefert nur mandantenspezifische Treffer; `run("kkrr", ...)` zitiert nur KKRR-Dokumente.

**Ablauf / lokale Variablen:**
- `globex_hits` / `acme_hits` — Suche mit `min_score=0.0`
- `llm` — `_FinalAnswerLLM` mit Tool-Call `search_knowledge_base` dann finale Antwort `"KKRR Antwort [1]."`
- `result` — `run`-Ergebnis; `result.sources[0]["title"] == "KKRR Firewall"`, kein BG-Ludwigshafen-Titel in Sources

**Aufrufer / Aufgerufene:** `search_knowledge_base`, `set_llm`, `run`, `set_llm(None)` in `finally`.

---

### `test_documents_api_lists_only_active_customer(client, db_session)`

**Beschreibung:** Dokument angelegt unter `bg-ludwigshafen`; nach Wechsel zu `kkrr` ist `GET /api/documents` leer.

**Ablauf / lokale Variablen:** User mit beiden Mandanten; `create` — POST text; `acme_list` / `globex_list` — Listing-JSON.

**Aufrufer / Aufgerufene:** Session- und Dokumenten-Routen in `routes.py`.

---

### `test_forbidden_customer_returns_403_on_scoped_operations(client, db_session)`

**Beschreibung:** User nur mit `kkrr` darf nicht auf `bg-ludwigshafen` wechseln; aktiver Mandant bleibt `kkrr`; Chat bleibt erlaubt (200).

**Ablauf / lokale Variablen:** `switch` — 403, Body `{"error": "forbidden_customer"}`; `GET /api/customers` → `active == "kkrr"`; `POST /api/chat` → 200.

**Aufrufer / Aufgerufene:** Mandanten-Session-Dependency in `routes.py`.

---

### `test_collection_name_rejects_invalid_slugs(invalid_slug)`

**Beschreibung:** Parametrisiert: ungültige Slugs werfen `ValueError` mit Message `invalid customer slug`.

**Parameter / Rückgabe:** `invalid_slug` — Werte: `"BG Ludwigshafen"`, `"../bad-slug"`, `"bad/b"`, `"bad b"`, `""`.

**Aufrufer / Aufgerufene:** `collection_name(invalid_slug)` in `customers.py`.

## (Optional) Tests

- **Fixtures:** `db_session`, `fake_vector_store`, `fake_embeddings` (letztere explizit in Ingestion/Search-Tests); `client` für HTTP-Tests; autouse KI-Mocks. Helfer: `create_customer`, `create_user`, `login`.
- **Abgedeckte Module:** `backend/app/ingestion.py`, `backend/app/retrieval.py`, `backend/app/agent.py`, `backend/app/customers.py`, `backend/app/routes.py`, `backend/app/qdrant_store.py`.

| Test | Intent |
|---|---|
| `test_ingestion_uses_separate_collections_per_customer` | Getrennte Qdrant-Collections und Payloads |
| `test_search_and_agent_scoped_to_active_customer` | Suche und Agent nur im aktiven Mandanten-Kontext |
| `test_documents_api_lists_only_active_customer` | Dokumentenliste mandantenscharf |
| `test_forbidden_customer_returns_403_on_scoped_operations` | Verbotener Mandantenwechsel → 403 |
| `test_collection_name_rejects_invalid_slugs` | Slug-Validierung für Collection-Namen |
