# `scripts/seed_production.py`

**Quellpfad:** `scripts/seed_production.py`

## Zweck und logischer Aufbau

CLI-Wrapper für **Produktions-Seed** mit sicherer Passwort-Eingabe: Passwort nie im Repo, nur per Env, CLI oder interaktivem `getpass` mit Bestätigung. Delegiert an `seed_setup.run_seed(profile="prod", …)`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `seed_setup.DEFAULT_ADMIN_EMAIL`, `run_seed`
- **Wird genutzt von:** `scripts/monitor_deploy.sh` (Deploy-Test); manuell auf Servern
- **Env:** `SEED_ADMIN_PASSWORD`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root (nur `sys.path` für `scripts`) |

## Funktionen und Klassen

### `parse_args() -> argparse.Namespace`

**Beschreibung:** `--email` (default `DEFAULT_ADMIN_EMAIL`), `--password` (optional).

---

### `_resolve_password(cli_password: str | None) -> str`

**Beschreibung:** Priorität: CLI → `SEED_ADMIN_PASSWORD` → doppeltes `getpass`.

**Ablauf:** Leeres Passwort oder nicht übereinstimmende Wiederholung → `SystemExit`.

---

### `main() -> None`

**Beschreibung:** `run_seed(profile="prod", email=args.email.strip().lower(), password=…)` und Erfolgsmeldung.
