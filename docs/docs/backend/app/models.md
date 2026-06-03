# `backend/app/models.py`

**Quellpfad:** `backend/app/models.py`

## Zweck und logischer Aufbau

**SQLAlchemy-ORM-Modelle** für SQLite: Benutzer, Mandanten, Dokumente, Chunks, Chat-Sessions und System-Prompts. Definiert außerdem die Hilfsfunktion `utc_now_iso()` für konsistente UTC-Zeitstempel als ISO-Strings mit `Z`-Suffix.

Lesereihenfolge: `utc_now_iso` → Kern-Entitäten (`User`, `Customer`, `UserCustomer`) → Wissensbasis (`Document`, `Chunk`) → Chat (`ChatSession`, `ChatMessage`) → `SystemPrompt`.

Die Modelle bilden die persistente Schicht für Auth, Mandantenisolation, RAG-Metadaten und Chat-Verlauf. Qdrant speichert Vektoren; `Chunk.qdrant_point_id` verknüpft SQL-Zeilen mit Qdrant-Punkten.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.db.Base`, SQLAlchemy (`Mapped`, `mapped_column`, `ForeignKey`, `relationship`, Spaltentypen)
- **Wird genutzt von:** `ingestion.py`, `routes.py`, `auth.py`, `tenant.py`, `chats.py`, `customers.py`, `users_admin.py`, `system_prompts.py`, `upload.py`, Seed-Skripte (`scripts/seed_*.py`), Tests
- **HTTP / UI / CLI:** indirekt über alle API-Routen, die DB-Entitäten lesen/schreiben
- **Daten:** SQLite-Tabellen `users`, `customers`, `user_customers`, `documents`, `chunks`, `chat_sessions`, `chat_messages`, `system_prompts`

## Konstanten, Typen und Modulebene

Keine Modul-Konstanten außer impliziten Tabellennamen in den Klassen.

## Funktionen und Klassen

### `utc_now_iso() -> str`

**Beschreibung:** Liefert aktuellen UTC-Zeitstempel als ISO-8601-String ohne Mikrosekunden, mit `Z` statt `+00:00`.

**Parameter / Rückgabe:** Keine Parameter; Rückgabe `str`.

**Ablauf / lokale Variablen:** `datetime.now(UTC)` mit Format-Anpassung.

**Aufrufer / Aufgerufene:** Aufgerufen in `ingestion.py`, `chats.py`, `customers.py`, `users_admin.py`, `system_prompts.py`, `upload.py`, Seed-Skripte, Tests.

---

### `User`

**Beschreibung:** Anwendungsbenutzer mit E-Mail, Passwort-Hash und Admin-Flags.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"users"` |
| `id` | `Mapped[str]` | Primary Key |
| `email` | `Mapped[str]` | Eindeutige E-Mail |
| `password_hash` | `Mapped[str]` | Gehashtes Passwort |
| `is_active` | `Mapped[int]` | 1 = aktiv |
| `is_admin` | `Mapped[int]` | 1 = Admin |
| `created_at` | `Mapped[str]` | ISO-Zeitstempel |
| `customers` | `Mapped[list["Customer"]]` | M:N über `user_customers` |

---

### `Customer`

**Beschreibung:** Mandant / Kunde mit Name und Aktiv-Flag.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"customers"` |
| `id` | `Mapped[str]` | Primary Key |
| `name` | `Mapped[str]` | Anzeigename |
| `active` | `Mapped[int]` | 1 = aktiv |
| `created_at` | `Mapped[str]` | ISO-Zeitstempel |
| `users` | `Mapped[list[User]]` | Zugeordnete Benutzer |
| `documents` | `Mapped[list["Document"]]` | Wissensdokumente |

---

### `UserCustomer`

**Beschreibung:** Assoziationstabelle Benutzer ↔ Kunde (Composite Primary Key).

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"user_customers"` |
| `user_id` | `Mapped[str]` | FK `users.id` |
| `customer_id` | `Mapped[str]` | FK `customers.id` |

---

### `SystemPrompt`

**Beschreibung:** System-Prompt pro Scope (global oder kundenspezifisch).

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"system_prompts"` |
| `scope` | `Mapped[str]` | Primary Key (z. B. `global`, `customer:{id}`) |
| `customer_id` | `Mapped[str \| None]` | Optional FK `customers.id` |
| `content` | `Mapped[str]` | Prompt-Text |
| `updated_at` | `Mapped[str]` | Letzte Änderung |
| `updated_by` | `Mapped[str]` | User-ID des Bearbeiters |

---

### `Document`

**Beschreibung:** Metadaten eines indizierten Wissensdokuments (Soft-Delete via `deleted_at`).

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"documents"` |
| `id` | `Mapped[str]` | Primary Key |
| `customer_id` | `Mapped[str]` | FK `customers.id` |
| `title` | `Mapped[str]` | Dokumenttitel |
| `source_type` | `Mapped[str]` | z. B. `manual`, `pdf`, `txt` |
| `source_url` | `Mapped[str \| None]` | Optionale URL-Quelle |
| `external_id` | `Mapped[str \| None]` | Externe Referenz |
| `original_filename` | `Mapped[str \| None]` | Upload-Dateiname |
| `mime_type` | `Mapped[str \| None]` | MIME-Typ |
| `storage_path` | `Mapped[str \| None]` | Pfad gespeicherter Datei |
| `source_text` | `Mapped[str \| None]` | Normalisierter Volltext für Admin-Bearbeitung |
| `chunk_count` | `Mapped[int]` | Anzahl Chunks |
| `status` | `Mapped[str]` | z. B. `indexed` |
| `error_message` | `Mapped[str \| None]` | Fehlertext bei Fehlschlag |
| `created_at` / `updated_at` | `Mapped[str]` | Zeitstempel |
| `deleted_at` | `Mapped[str \| None]` | Soft-Delete-Zeitpunkt |
| `customer` | `Mapped[Customer]` | Relationship |
| `chunks` | `Mapped[list["Chunk"]]` | Zugehörige Chunks |

---

### `Chunk`

**Beschreibung:** Textsegment eines Dokuments mit Qdrant-Verknüpfung.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"chunks"` |
| `id` | `Mapped[str]` | Primary Key (= Qdrant-Punkt-ID) |
| `document_id` | `Mapped[str]` | FK `documents.id` |
| `customer_id` | `Mapped[str]` | Mandanten-ID (denormalisiert) |
| `chunk_index` | `Mapped[int]` | Position im Dokument |
| `text` | `Mapped[str]` | Chunk-Plaintext |
| `token_estimate` | `Mapped[int \| None]` | Grobe Token-Schätzung |
| `qdrant_point_id` | `Mapped[str]` | Qdrant-Punkt-ID |
| `created_at` | `Mapped[str]` | Erstellungszeitpunkt |
| `document` | `Mapped[Document]` | Relationship |

---

### `ChatSession`

**Beschreibung:** Chat-Session eines Benutzers in einem Mandantenkontext.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"chat_sessions"` |
| `id` | `Mapped[str]` | Primary Key |
| `user_id` | `Mapped[str]` | FK `users.id` |
| `customer_id` | `Mapped[str]` | FK `customers.id` |
| `title` | `Mapped[str]` | Session-Titel (Default `"Neuer Chat"`) |
| `created_at` / `updated_at` | `Mapped[str]` | Zeitstempel |
| `messages` | `Mapped[list["ChatMessage"]]` | Nachrichten, Cascade delete-orphan |

---

### `ChatMessage`

**Beschreibung:** Einzelne Chat-Nachricht in einer Session.

| Attribut | Typ | Beschreibung |
|---|---|---|
| `__tablename__` | — | `"chat_messages"` |
| `id` | `Mapped[str]` | Primary Key |
| `session_id` | `Mapped[str]` | FK `chat_sessions.id` |
| `role` | `Mapped[str]` | z. B. `user`, `assistant` |
| `content` | `Mapped[str]` | Nachrichtentext |
| `sources_json` | `Mapped[str \| None]` | Serialisierte Quellen |
| `no_context` | `Mapped[int]` | 1 wenn ohne KB-Kontext geantwortet |
| `created_at` | `Mapped[str]` | Zeitstempel |
| `session` | `Mapped[ChatSession]` | Relationship |
