# `scripts/seed_kb.py`

**Quellpfad:** `scripts/seed_kb.py`

## Zweck und logischer Aufbau

Befüllt die Wissensbasis mit **mandantenspezifischen Demo-Texten** über `ingest_text` (Embeddings + Qdrant). Erfordert gültigen `OPENAI_API_KEY` und erreichbaren Qdrant. Jeder Eintrag in `KB_ENTRIES` ist klar einem `customer_id` zugeordnet (Sichtbarkeit der Mandantenisolation).

Ablauf: `init_db` → pro Eintrag `ingest_text` → Ausgabe Chunk-Anzahl oder `IngestionError`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.db.SessionLocal`, `init_db`; `app.ingestion.ingest_text`, `IngestionError`; `seed_data.PRODUCTION_CUSTOMERS` (nur für Log-Ausgabe der Slugs)
- **Wird genutzt von:** manuell / Doku-Hinweis in `setup.py` (`docker compose exec api python scripts/seed_kb.py`)
- **Daten:** SQLite Dokumente/Chunks; Qdrant-Vektoren pro Mandant

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root |
| `KB_ENTRIES` | `tuple[tuple[str, str, str], ...]` | Pro Eintrag: `(customer_id, title, text)` — vier Demo-Runbooks (BG Ludwigshafen, BG Frankfurt, Detmold Lippe, KKRR) |

## Funktionen und Klassen

### `seed_kb(entries: tuple[tuple[str, str, str], ...] = KB_ENTRIES) -> None`

**Beschreibung:** Indexiert jeden Demo-Text mit `source_type="manual"`.

**Parameter / Rückgabe:** `entries` — Mandant, Titel, Body; kein Return.

**Ablauf / lokale Variablen:** `result` — Rückgabe von `ingest_text` mit `document.chunk_count` und `document.id`; bei Fehler nur Print, kein Abbruch der Schleife.

**Aufrufer / Aufgerufene:** `ingest_text(db, customer_id=…, title=…, text=…, source_type="manual")`.

---

`__main__`: druckt Kundenliste aus `PRODUCTION_CUSTOMERS`, ruft `seed_kb()` auf.
