# `scripts/seed_data.py`

**Quellpfad:** `scripts/seed_data.py`

## Zweck und logischer Aufbau

Gemeinsame **Datendefinitionen** für alle Seed-Skripte: Mandanten-Slugs und Anzeigenamen, Standard-Admin-E-Mail-Set, Default-Passwort und ein vordefiniertes Admin-User-Dict. Enthält keine `main()`-Funktion — wird von `seed_customers.py`, `seed_users.py`, `seed_setup.py` und `seed_kb.py` importiert.

Lesereihenfolge: Konstanten-Tupel → `ALL_CUSTOMERS` → `ADMIN_EMAILS` → `DEFAULT_USERS`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** keine App-Module (reine Daten)
- **Wird genutzt von:** `scripts/seed_customers.py`, `scripts/seed_users.py`, `scripts/seed_setup.py`, `scripts/seed_kb.py`
- **Daten:** Slugs entsprechen späteren `Customer.id`-Werten in SQLite

## Konstanten, Typen und Modulebene

| Name | Art | Beschreibung |
|---|---|---|
| `GLOBAL_CUSTOMER` | `tuple[str, str]` | `("global", "Global")` — globaler Mandant |
| `PRODUCTION_CUSTOMERS` | `tuple[tuple[str, str], ...]` | Vier Produktions-Mandanten (BG Ludwigshafen, BG Frankfurt, Detmold Lippe, KKRR) |
| `ALL_CUSTOMERS` | `tuple` | `GLOBAL_CUSTOMER` + `PRODUCTION_CUSTOMERS` |
| `ADMIN_EMAILS` | `frozenset[str]` | `admin@example.com`, `matthias.schindler@maris-healthcare.de` — werden bei `seed_defaults` ggf. zum Admin befördert |
| `DEFAULT_PASSWORD` | `str` | `"GeheimesPW!"` — nur für Default-Seed-User |
| `DEFAULT_USERS` | `tuple[dict, ...]` | Ein Eintrag: Admin mit Zugriff auf alle `PRODUCTION_CUSTOMERS`-Slugs |

## Funktionen und Klassen

Keine Funktionen oder Klassen — nur Modul-Konstanten.
