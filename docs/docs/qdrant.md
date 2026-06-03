# `qdrant.yaml`

**Quellpfad:** `qdrant.yaml`

## Zweck

Statische **Qdrant-Server-Konfiguration** für einen nativen Qdrant-Prozess (Speicherpfad, Bind-Host, HTTP- und gRPC-Ports). Im Repo nicht von `docker-compose.yml` referenziert — der Compose-Service `qdrant` nutzt das Image `qdrant/qdrant:latest` mit eigenen Volume-Mounts.

## Ablauf (kurz)

1. Definiert Speicherort und Netzwerk-Bindung für einen Qdrant-Server-Prozess außerhalb des Compose-Stacks (im Repo keine `source`- oder Compose-Referenz auf diese Datei).
2. `storage.storage_path` → `./data/qdrant_storage`.
3. `service.host` `127.0.0.1`, `http_port` `6333`, `grpc_port` `6334`.

## Konfiguration / Parameter

| Abschnitt | Schlüssel | Wert |
|---|---|---|
| `storage` | `storage_path` | `./data/qdrant_storage` |
| `service` | `host` | `127.0.0.1` |
| `service` | `http_port` | `6333` |
| `service` | `grpc_port` | `6334` |

## Siehe auch

- [`docs/docs/docker-compose.md`](./docker-compose.md) — Qdrant als Docker-Service (Port 6333)
- [`docs/docs/docker-compose.dev-local.md`](./docker-compose.dev-local.md) — Dev-Overlay Port `6334:6333`
- [`docs/docs/backend/app/qdrant_store.md`](./backend/app/qdrant_store.md) — Anwendungs-Client zu Qdrant
