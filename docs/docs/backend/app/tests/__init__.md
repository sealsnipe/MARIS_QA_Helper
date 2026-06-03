# `backend/app/tests/__init__.py`

**Quellpfad:** `backend/app/tests/__init__.py`

## Zweck

Leere Datei, die das Verzeichnis `backend/app/tests/` als Python-Paket `app.tests` kennzeichnet. Sie enthält weder Importe noch Testlogik. Pytest entdeckt Testmodule (`test_*.py`) direkt; dieses Paket ermöglicht zusätzlich Imports wie `from app.tests.conftest import create_user`.

## Ablauf (kurz)

1. Beim Import von `app.tests.*` erkennt Python `tests/` als Unterpaket von `app`.
2. Keine Laufzeit-Initialisierung — die Datei ist leer.
3. Gemeinsame Fixtures und Hilfsfunktionen liegen in `conftest.py` im selben Verzeichnis.

## Konfiguration / Parameter

Keine — keine Env-Variablen, CLI-Args oder Symbole definiert.

## Siehe auch

- [`backend/app/tests/conftest.md`](./conftest.md) — pytest-Fixtures und Test-Hilfsfunktionen
- [`backend/app/__init__.py.md`](../__init__.py.md) — übergeordnetes App-Paket
