# `.github/workflows/test.yml`

**Quellpfad:** `.github/workflows/test.yml`

## Zweck

CI-Workflow (GitHub Actions) um Regressionen wie F1 (unbemerkte Test-Reduktionen) zu verhindern. Läuft auf Push/PR zu `main`: Python 3.12, installiert Backend editable, führt `pytest -q` aus (ohne Netz, dank Mocks in `conftest.py`).

Zusätzlich optionaler Job `docker-smoke` zum Bauen des Backend-Images (fängt Dockerfile-Drift, fehlende apt-Pakete wie poppler-utils).

## Ablauf (kurz)

1. checkout
2. setup-python 3.12
3. `pip install -e backend`
4. `cd backend && PYTHONPATH=. python -m pytest -q`
5. (docker-smoke) `docker build -t ... ./backend`

## Konfiguration / Parameter

- Trigger: `push`/`pull_request` auf `main`
- Matrix: nur ubuntu-latest + py 3.12 (deterministisch, keine Secrets nötig)
- Annahme: Tests sind netz-unabhängig (wie in `docs/10_testing_strategy.md` und `PROJECT_STANDARDS.md` gefordert)

## Siehe auch

- [`docs/PROJECT_STANDARDS.md`](../../PROJECT_STANDARDS.md) — Test-Pflicht + Tenant-Isolation
- [`docs/10_testing_strategy.md`](../../10_testing_strategy.md)
- `backend/Dockerfile` (poppler, pytest im Image — separate Dedup später)
- Review 2026-06-09 (F6 CI als Gegenmaßnahme zu wiederholten Regressionen)
