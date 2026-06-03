# `scripts/update.sh`

**Quellpfad:** `scripts/update.sh`

## Zweck

Aktualisiert eine bereits deployte Instanz nach `git pull`: Images neu bauen, Container neu starten, Health prüfen — ohne vorheriges manuelles `stop.sh`.

## Ablauf (kurz)

1. Repo-Root, `compose_env` aus `compose_env.sh`.
2. `git pull --ff-only`.
3. `compose_run up -d --build`.
4. Health-Check auf `http://127.0.0.1:${APP_PORT:-8088}/api/health`.

## Konfiguration / Parameter

| Quelle | Bedeutung |
|---|---|
| `.env` / `compose_env.sh` | Compose-Profil und Services |
| `APP_PORT` | Default `8088` |

## Siehe auch

- [`start.md`](./start.md)
- [`stop.md`](./stop.md)
- [`compose_env.md`](./compose_env.md)
