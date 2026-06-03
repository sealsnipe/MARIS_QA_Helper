# `scripts/import_codex_auth.py`

**Quellpfad:** `scripts/import_codex_auth.py`

## Zweck und logischer Aufbau

Importiert OAuth-Tokens aus der **Codex CLI**-Datei `auth.json` und schreibt sie im Format von **oauth-codex** nach `~/.oauth_codex/auth.json` — für Chat-Smoke-Tests und Setup mit `LLM_AUTH_MODE=chatgpt_oauth`.

Ablauf: Quellpfad auflösen → JSON laden → in Zielformat mappen (inkl. JWT-`exp`) → Datei mit restriktiven Rechten (`0600`) schreiben.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** Standardbibliothek (`json`, `base64`, `pathlib`, `argparse`)
- **Wird genutzt von:** manuell vor `smoke_chat_oauth.py`; alternative zu `login_chat_oauth.py` wenn Codex bereits eingeloggt
- **Dateisystem:** `CODEX_HOME/auth.json`, `~/.oauth_codex/auth.json`, optional `/mnt/c/Users/Matthias/.codex/auth.json`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root |
| `DEFAULT_SOURCE` | `Path` | `$CODEX_HOME/auth.json` oder `~/.codex/auth.json` |
| `DEFAULT_TARGET` | `Path` | `~/.oauth_codex/auth.json` |
| `WINDOWS_FALLBACK` | `Path` | Feste WSL-Pfad-Variante für Windows-Codex-Auth |

## Funktionen und Klassen

### `_resolve_source(path: Path | None) -> Path`

**Beschreibung:** CLI-Pfad, sonst `DEFAULT_SOURCE`, sonst `WINDOWS_FALLBACK` falls existiert.

---

### `_load_codex_auth(path: Path) -> dict`

**Beschreibung:** Liest JSON; bricht ab wenn kein `dict`.

---

### `_jwt_expires_at(access_token: str) -> float | None`

**Beschreibung:** Dekodiert JWT-Payload (Base64url), liest Claim `exp`.

---

### `_to_oauth_codex_payload(codex_auth: dict) -> dict`

**Beschreibung:** Normalisiert Token-Felder: `tokens`-Unterdict oder Top-Level `access_token`; setzt `expires_at`, optional `api_key` aus `OPENAI_API_KEY` im Codex-File.

**Ablauf / lokale Variablen:** `source` — gewähltes Token-Dict.

---

### `import_auth(source, target, *, force: bool) -> None`

**Beschreibung:** Schreibt Zieldatei; ohne `--force` Abbruch wenn Ziel existiert.

---

### `parse_args() -> argparse.Namespace`

**Beschreibung:** `--source`, `--target`, `--force`.

---

### `main() -> None`

**Beschreibung:** `import_auth(_resolve_source(args.source), args.target.expanduser(), force=…)`.
