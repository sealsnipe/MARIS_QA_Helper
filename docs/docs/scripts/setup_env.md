# `scripts/setup_env.py`

**Quellpfad:** `scripts/setup_env.py`

## Zweck und logischer Aufbau

Schlankes Tool zum **Anlegen oder Aktualisieren** der lokalen `.env`: OpenAI-API-Key und `SESSION_SECRET` — ohne vollständigen Setup-Wizard. Liest bei fehlender `.env` aus `.env.example`. Modus `--check-only` validiert ohne Schreiben.

Reihenfolge: Pfad-Konstanten → Lese/Schreib-Helfer → Validierung → `parse_args` → `main`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** Standardbibliothek (`secrets`, `re`, `argparse`)
- **Wird genutzt von:** manuell; empfohlen vor `smoke_openai.py` und als Vorstufe zu `setup.py`
- **Dateisystem:** `ROOT/.env`, `ROOT/.env.example`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root |
| `ENV_PATH` | `Path` | `.env` |
| `EXAMPLE_PATH` | `Path` | `.env.example` |
| `PLACEHOLDER_KEY` | `str` | `sk-placeholder-replace-me` |
| `KEY_PATTERN` | `re.Pattern` | Validiert `sk-…`-Keys |

## Funktionen und Klassen

### `_read_lines(path: Path) -> list[str]`

**Beschreibung:** Liest Env-Zeilen; `SystemExit` wenn Datei fehlt.

---

### `_write_env(lines: list[str]) -> None`

**Beschreibung:** Schreibt `.env` mit trailing Newline.

---

### `_upsert(lines, key, value) -> list[str]`

**Beschreibung:** Ersetzt oder hängt `KEY=value` an.

---

### `_validate_openai_key(value: str) -> str`

**Beschreibung:** Lehnt Platzhalter ab; prüft Regex.

---

### `_mask_key_preview(key: str) -> str`

**Beschreibung:** Kurze Anzeige für Bestätigung (Anfang/Ende).

---

### `_prompt_openai_key_interactive() -> str`

**Beschreibung:** Schleife bis gültiger Key eingegeben.

---

### `parse_args() -> argparse.Namespace`

**Beschreibung:** `--openai-key`, `--from-env`, `--regenerate-session-secret`, `--check-only`.

---

### `main() -> None`

**Beschreibung:** Liest aktuelle Key/Secret aus Zeilen; `--check-only` prüft `key_ok` und `secret_ok` (Secret min. 32 Zeichen, kein `change-me`); sonst setzt Key/Secret bei Bedarf und schreibt nur bei Änderungen. Abschluss-Hinweis auf `setup.py` und `smoke_openai.py`.
