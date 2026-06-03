# `scripts/seed_setup.py`

**Quellpfad:** `scripts/seed_setup.py`

## Zweck und logischer Aufbau

Orchestriert **Kunden- und Admin-Seed** für Setup und Dev: ruft `seed_customers` und `seed_user` in fester Reihenfolge auf. Profil `dev` vs. `prod` nutzt dieselbe Kundenmenge (`profile` wird in `run_seed` ignoriert, nur für CLI-Kompatibilität).

Einstieg: `run_seed` (von `setup.py`, `dev_local.sh`, `seed_production.py`) oder CLI mit `--profile`, `--email`, `--password`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `seed_customers.seed_customers`; `seed_users.seed_user`; `seed_data.GLOBAL_CUSTOMER`, `PRODUCTION_CUSTOMERS`
- **Wird genutzt von:** `scripts/setup.py`, `scripts/seed_production.py`, `scripts/dev_local.sh`
- **CLI:** `python scripts/seed_setup.py --profile dev|prod --email … --password …`

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `ROOT` | `Path` | Repo-Root |
| `DEFAULT_ADMIN_EMAIL` | `str` | `matthias.schindler@maris-healthcare.de` |
| `DeployProfile` | `Literal["dev", "prod"]` | Typalias für Profil |

## Funktionen und Klassen

### `run_seed(*, profile: DeployProfile, email: str, password: str) -> None`

**Beschreibung:** Seedet alle Kunden (`GLOBAL` + Produktion) und einen Admin mit Zugriff auf alle Produktions-Slugs.

**Parameter / Rückgabe:** `profile` — ungenutzt (`_ = profile`); `email` normalisiert lowercase; `password` Klartext für `seed_user`.

**Ablauf / lokale Variablen:** `customers` — volles Tuple; `customer_ids` — nur Slugs aus `PRODUCTION_CUSTOMERS`.

**Aufrufer / Aufgerufene:** `seed_customers(customers)`, `seed_user(normalized, password, customer_ids, is_admin=True)`.

---

### `parse_args() -> argparse.Namespace`

**Beschreibung:** `--profile` (default `dev`), `--email` (Env `SEED_ADMIN_EMAIL`), `--password` (Env `SEED_ADMIN_PASSWORD`).

---

### `main() -> None`

**Beschreibung:** Beendet mit `SystemExit`, wenn Passwort leer; sonst `run_seed`.
