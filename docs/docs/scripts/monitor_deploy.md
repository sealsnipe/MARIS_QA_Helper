# `scripts/monitor_deploy.sh`

**Quellpfad:** `scripts/monitor_deploy.sh`

## Zweck

Hilfsskript auf dem Windows-Host: startet eine vollständige Produktions-Installation in einer WSL-Distro im Hintergrund, schreibt alles in eine Logdatei und zeigt während des Laufs regelmäßig die letzten Logzeilen. Dient dem manuellen Deploy-Monitoring, nicht dem täglichen Betrieb der App.

## Ablauf (kurz)

1. Parameter: WSL-Distro-Name (Default `MARISDeployTest`), Logpfad (Default `/tmp/maris-deploy-<distro>.log`).
2. `OPENAI_API_KEY` aus Umgebung oder aus fest verdrahtetem `.env`-Pfad per Python-One-Liner.
3. Logdatei leeren, dann `wsl.exe -d <distro>` mit Remote-Bash: Repo klonen, `install.sh --non-interactive --profile prod … --start`, Health-Check, `seed_production.py`, Marker `MARIS_DEPLOY_OK`.
4. Hintergrundprozess: alle 15 s `tail -n 8` des Logs; nach Ende `tail -n 30` und `grep MARIS_DEPLOY_OK`.

## Konfiguration / Parameter

| Name | Default | Bedeutung |
|---|---|---|
| `$1` | `MARISDeployTest` | WSL-Distro |
| `$2` | `/tmp/maris-deploy-…` | Logdatei |
| `OPENAI_API_KEY` | — | Key für `install.sh` |

## Siehe auch

- [`install.md`](../install.md) — wird in WSL aufgerufen
- [`seed_production.md`](./seed_production.md)
- [`docs/11_setup_and_operations.md`](../../11_setup_and_operations.md) (falls vorhanden)
