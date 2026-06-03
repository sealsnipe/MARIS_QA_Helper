#!/usr/bin/env python3
"""Interactive first-time setup: env, credentials, deploy profile, Docker start."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"
COMPOSE_BASE = ROOT / "docker-compose.yml"
COMPOSE_PROD = ROOT / "docker-compose.prod.yml"
COMPOSE_OAUTH = ROOT / "docker-compose.oauth.yml"
DEFAULT_OAUTH_PATH = Path.home() / ".oauth_codex" / "auth.json"

PLACEHOLDER_KEY = "sk-placeholder-replace-me"
KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{10,}$")

CHAT_MODEL_API = "gpt-4.1-mini"
CHAT_MODEL_OAUTH = "gpt-5.4-mini"

DeployProfile = Literal["dev", "prod"]
Runtime = Literal["docker", "local"]
LlmAuthMode = Literal["api_key", "chatgpt_oauth"]


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    return path.read_text(encoding="utf-8").splitlines()


def _write_env(lines: list[str]) -> None:
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  → {ENV_PATH}")


def _upsert(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    replaced = False
    updated: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            updated.append(f"{prefix}{value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"{prefix}{value}")
    return updated


def _get_value(lines: list[str], key: str, default: str = "") -> str:
    prefix = f"{key}="
    for line in lines:
        if line.startswith(prefix):
            return line.split("=", 1)[1]
    return default


def _validate_openai_key(value: str) -> str:
    cleaned = value.strip()
    if cleaned in {PLACEHOLDER_KEY, "sk-...", "sk-your-key-here"}:
        raise ValueError("Platzhalter-Key — bitte echten OpenAI API-Key eingeben.")
    if not KEY_PATTERN.fullmatch(cleaned):
        raise ValueError("OpenAI-Key muss wie sk-... aussehen (ohne Leerzeichen).")
    return cleaned


def _prompt_yes_no(question: str, default: bool = False) -> bool:
    suffix = "[J/n]" if default else "[j/N]"
    while True:
        raw = input(f"{question} {suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in {"j", "ja", "y", "yes"}:
            return True
        if raw in {"n", "nein", "no"}:
            return False
        print("  Bitte j oder n eingeben.")


def _prompt_choice(question: str, options: list[tuple[str, str]]) -> str:
    print(question)
    for idx, (key, label) in enumerate(options, start=1):
        print(f"  [{idx}] {label}")
    while True:
        raw = input("Auswahl: ").strip()
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
        keys = {key for key, _ in options}
        if raw in keys:
            return raw
        print("  Ungültige Auswahl.")


def _check_prerequisites(
    *,
    skip_docker: bool,
    runtime: Runtime,
    interactive: bool,
    auto_install_docker: bool,
):
    print("\n=== Voraussetzungen ===\n")
    py = sys.version_info
    if py < (3, 12):
        print(f"  ⚠ Python {py.major}.{py.minor} — empfohlen: 3.12+")
    else:
        print(f"  ✓ Python {py.major}.{py.minor}")

    if runtime == "local":
        print("  ○ Docker optional (lokaler Start mit uvicorn)")
        return None

    if skip_docker:
        print("  ○ Docker-Check übersprungen")
        return None

    sys.path.insert(0, str(ROOT / "scripts"))
    from docker_preflight import check_docker, ensure_docker, print_docker_status

    status = ensure_docker(
        interactive=interactive,
        auto_install=auto_install_docker,
        skip_install=False,
    )
    print_docker_status(status)
    return status


def _require_docker_ready(status) -> None:
    from docker_preflight import assert_docker_ready

    assert_docker_ready(status, context="Docker Compose Start")


def _ensure_env_file() -> list[str]:
    if ENV_PATH.exists():
        print(f"\n  Vorhandene {ENV_PATH.name} wird aktualisiert.")
        return _read_lines(ENV_PATH)
    if not EXAMPLE_PATH.exists():
        raise SystemExit(f"Fehlt: {EXAMPLE_PATH}")
    shutil.copy(EXAMPLE_PATH, ENV_PATH)
    print(f"\n  {EXAMPLE_PATH.name} → {ENV_PATH.name}")
    return _read_lines(ENV_PATH)


def _resolve_deploy_profile(args: argparse.Namespace) -> DeployProfile:
    if args.profile:
        return args.profile
    if args.non_interactive:
        return "prod" if args.production else "dev"
    return _prompt_choice(
        "\nEinsatzumgebung?",
        [
            ("dev", "Entwicklung — WSL/lokal, HTTP ok"),
            ("prod", "Produktion — Server hinter HTTPS-Proxy"),
        ],
    )


def _resolve_runtime(args: argparse.Namespace, profile: DeployProfile) -> Runtime:
    if args.runtime:
        return args.runtime
    if args.non_interactive:
        return "docker"
    default_docker = profile == "prod"
    choice = _prompt_choice(
        "\nWie starten?",
        [
            ("docker", "Docker Compose (api + qdrant) — empfohlen"),
            ("local", "Nur .env — uvicorn + Qdrant manuell"),
        ],
    )
    return choice  # type: ignore[return-value]


def _resolve_llm_mode(args: argparse.Namespace, profile: DeployProfile) -> LlmAuthMode:
    if args.llm_auth_mode:
        return args.llm_auth_mode
    if args.non_interactive:
        return "api_key" if profile == "prod" else args.llm_auth_mode or "chatgpt_oauth"
    if profile == "prod":
        print("\nProduktion: OpenAI API-Key für Chat empfohlen (OAuth im Container ist umständlich).")
    choice = _prompt_choice(
        "\nWie soll der Chat-Agent authentifizieren?",
        [
            ("chatgpt_oauth", "ChatGPT OAuth — Browser-Login (Codex/Plus, Dev/WSL)"),
            ("api_key", "OpenAI API-Key — Platform-Billing (Produktion/Docker)"),
        ],
    )
    if profile == "prod" and choice == "chatgpt_oauth":
        if not _prompt_yes_no("  OAuth in Produktion ist unüblich. Trotzdem OAuth?", default=False):
            return "api_key"
    return choice  # type: ignore[return-value]


def _prompt_embedding_key(
    lines: list[str],
    *,
    openai_key: str | None,
    interactive: bool = True,
) -> tuple[list[str], str]:
    print("\n=== Embeddings (OpenAI API-Key) ===\n")
    print(
        "Für die Wissensdatenbank-Suche werden Vektoren berechnet — dafür ist immer\n"
        "ein OpenAI API-Key nötig (Platform-Billing, unabhängig vom Chat-Modus).\n"
    )

    current = _get_value(lines, "OPENAI_API_KEY")
    key = openai_key
    if key:
        key = _validate_openai_key(key)
    elif current and current != PLACEHOLDER_KEY and KEY_PATTERN.fullmatch(current):
        if _prompt_yes_no(f"Vorhandenen Embedding-Key behalten ({current[:8]}…)?", default=True):
            key = current
    if not key:
        if not interactive:
            raise SystemExit("--non-interactive braucht --openai-key")
        while True:
            entered = getpass.getpass("OpenAI API-Key für Embeddings (sk-..., versteckt): ").strip()
            if not entered:
                print("  Key ist Pflicht.")
                continue
            try:
                key = _validate_openai_key(entered)
                break
            except ValueError as exc:
                print(f"  {exc}")

    lines = _upsert(lines, "OPENAI_API_KEY", key)
    return lines, key


def _configure_chat_api_key(lines: list[str]) -> list[str]:
    print("\n=== Chat: OpenAI API-Key ===\n")
    print("Chat und Agent nutzen denselben OPENAI_API_KEY wie die Embeddings.")
    lines = _upsert(lines, "LLM_AUTH_MODE", "api_key")
    lines = _upsert(lines, "CHAT_MODEL", CHAT_MODEL_API)
    return lines


def _configure_chat_oauth(lines: list[str], *, oauth_path: Path, skip_login: bool) -> list[str]:
    print("\n=== Chat: ChatGPT OAuth (Codex-Abo) ===\n")
    print(
        "Login im Browser mit Einmalcode — wie bei Codex CLI.\n"
        "Embeddings bleiben beim API-Key oben.\n"
    )
    lines = _upsert(lines, "LLM_AUTH_MODE", "chatgpt_oauth")
    lines = _upsert(lines, "CHAT_MODEL", CHAT_MODEL_OAUTH)
    lines = _upsert(lines, "CODEX_OAUTH_AUTH_PATH", str(oauth_path))

    if skip_login:
        if oauth_path.exists():
            print(f"  ✓ OAuth-Datei vorhanden: {oauth_path}")
        else:
            print(f"  ⚠ Keine OAuth-Datei unter {oauth_path}")
            print("     Später: python3 scripts/login_chat_oauth.py")
        return lines

    if oauth_path.exists() and _prompt_yes_no(f"Vorhandene OAuth-Session behalten ({oauth_path})?", default=True):
        return lines

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from login_chat_oauth import login_device_code
    except ImportError as exc:
        raise SystemExit(
            "login_chat_oauth.py nicht ladbar. Bitte httpx installieren:\n"
            "  pip install httpx"
        ) from exc

    login_device_code(oauth_path)
    if not oauth_path.exists():
        raise SystemExit("OAuth-Login abgeschlossen, aber auth.json fehlt.")
    print(f"  ✓ OAuth gespeichert: {oauth_path}")
    return lines


def _configure_runtime(lines: list[str], *, runtime: Runtime) -> list[str]:
    if runtime == "local":
        lines = _upsert(lines, "QDRANT_URL", "http://127.0.0.1:6333")
        print("\n  QDRANT_URL → http://127.0.0.1:6333 (lokal)")
    else:
        lines = _upsert(lines, "QDRANT_URL", "http://qdrant:6333")
    return lines


def _configure_deploy(lines: list[str], *, profile: DeployProfile) -> list[str]:
    secure = "true" if profile == "prod" else "false"
    lines = _upsert(lines, "SESSION_COOKIE_SECURE", secure)
    if profile == "prod":
        print("\n  SESSION_COOKIE_SECURE → true (HTTPS-Proxy vorausgesetzt)")
    return lines


def _ensure_session_secret(lines: list[str]) -> list[str]:
    current = _get_value(lines, "SESSION_SECRET")
    weak = not current or "change-me" in current or len(current) < 32
    if weak:
        lines = _upsert(lines, "SESSION_SECRET", secrets.token_urlsafe(48))
        print("\n  SESSION_SECRET generiert.")
    return lines


def _compose_command(profile: DeployProfile, llm_mode: LlmAuthMode, oauth_path: Path) -> list[str]:
    if not COMPOSE_BASE.exists():
        raise SystemExit(f"Fehlt: {COMPOSE_BASE}")

    cmd = ["docker", "compose", "-f", str(COMPOSE_BASE)]
    if profile == "prod":
        if not COMPOSE_PROD.exists():
            raise SystemExit(f"Fehlt: {COMPOSE_PROD}")
        cmd.extend(["-f", str(COMPOSE_PROD)])
    elif llm_mode == "chatgpt_oauth":
        if not COMPOSE_OAUTH.exists():
            raise SystemExit(f"Fehlt: {COMPOSE_OAUTH}")
        cmd.extend(["-f", str(COMPOSE_OAUTH)])
    cmd.extend(["up", "--build", "-d"])
    return cmd


def _compose_env(profile: DeployProfile, llm_mode: LlmAuthMode, oauth_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    if profile != "prod" and llm_mode == "chatgpt_oauth":
        if not oauth_path.exists():
            raise SystemExit(
                f"OAuth-Datei fehlt: {oauth_path}\n"
                "Erst OAuth-Login abschließen oder LLM_AUTH_MODE=api_key wählen."
            )
        env["OAUTH_AUTH_HOST_PATH"] = str(oauth_path.resolve())
    return env


def _format_compose_hint(cmd: list[str], env: dict[str, str]) -> str:
    prefix = ""
    if "OAUTH_AUTH_HOST_PATH" in env:
        prefix = f"OAUTH_AUTH_HOST_PATH={shlex.quote(env['OAUTH_AUTH_HOST_PATH'])} "
    return prefix + " ".join(shlex.quote(part) for part in cmd)


def _maybe_start_compose(
    *,
    start: bool | None,
    runtime: Runtime,
    profile: DeployProfile,
    llm_mode: LlmAuthMode,
    oauth_path: Path,
    docker_status,
) -> None:
    if runtime == "local":
        print("\n  Lokaler Modus — Docker Compose übersprungen.")
        return
    if start is False:
        return
    if start is None and not _prompt_yes_no("\nDocker Compose jetzt starten (api + qdrant)?", default=True):
        return

    if docker_status is not None:
        _require_docker_ready(docker_status)

    if not shutil.which("docker"):
        print("  Docker nicht installiert — übersprungen.")
        return

    print("\n=== Docker Compose ===\n")
    try:
        cmd = _compose_command(profile, llm_mode, oauth_path)
        env = _compose_env(profile, llm_mode, oauth_path)
    except SystemExit as exc:
        print(f"  {exc}")
        return

    print(f"  $ {_format_compose_hint(cmd, env)}")
    try:
        subprocess.run(cmd, cwd=ROOT, check=True, env=env)
    except subprocess.CalledProcessError:
        print("  docker compose fehlgeschlagen.")
        print(f"  Manuell: {_format_compose_hint(cmd, env)}")
        return

    print("  ✓ Stack gestartet — http://127.0.0.1:8088")
    print("  Health: curl http://127.0.0.1:8088/api/health")


def _print_next_steps(
    *,
    profile: DeployProfile,
    runtime: Runtime,
    llm_mode: LlmAuthMode,
    oauth_path: Path,
) -> None:
    print("\n=== Fertig ===\n")
    print("Nächste Schritte:")

    if runtime == "docker":
        print("  • Prod-Seed:    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \\")
        print("                    python scripts/seed_production.py")
        print("  • Updates:      ./scripts/update.sh")
        if profile == "prod":
            print("  • Prod-Stack:   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d")
        elif llm_mode == "chatgpt_oauth":
            host_path = oauth_path.resolve()
            print(
                "  • OAuth-Stack:  "
                f"OAUTH_AUTH_HOST_PATH={host_path} "
                "docker compose -f docker-compose.yml -f docker-compose.oauth.yml up -d"
            )
    else:
        print("  • Qdrant starten (z. B. docker run -p 6333:6333 qdrant/qdrant)")
        print("  • API starten:  cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8088")

    if llm_mode == "chatgpt_oauth":
        print("  • OAuth-Test:   python3 scripts/smoke_chat_oauth.py")
    else:
        print("  • API-Test:     python3 scripts/smoke_openai.py")
    print("  • Tests:        cd backend && PYTHONPATH=. pytest -q")
    print("  • Env prüfen:   python3 scripts/setup_env.py --check-only")

    if profile == "prod":
        print("\n  Produktion: Reverse-Proxy (Caddy/nginx) vor Port 8088, nur 443/80 öffnen.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MARIS Q/A Helper — interaktives Erst-Setup (.env + Chat-Auth + Deploy)",
    )
    parser.add_argument("--openai-key", help="OpenAI API-Key (Embeddings); sonst interaktiv")
    parser.add_argument(
        "--llm-auth-mode",
        choices=("api_key", "chatgpt_oauth"),
        help="Chat-Authentifizierung (sonst interaktive Auswahl)",
    )
    parser.add_argument(
        "--profile",
        choices=("dev", "prod"),
        help="dev (lokal) oder prod (HTTPS-Server)",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Kurzform für --profile prod (non-interactive)",
    )
    parser.add_argument(
        "--runtime",
        choices=("docker", "local"),
        help="docker (Compose) oder local (nur .env, uvicorn manuell)",
    )
    parser.add_argument(
        "--oauth-path",
        type=Path,
        default=DEFAULT_OAUTH_PATH,
        help=f"Ziel für OAuth-Tokens (Default: {DEFAULT_OAUTH_PATH})",
    )
    parser.add_argument("--skip-oauth-login", action="store_true", help="OAuth nur in .env eintragen")
    parser.add_argument("--skip-docker-check", action="store_true")
    parser.add_argument(
        "--install-docker",
        action="store_true",
        help="Docker Engine + Compose per apt installieren falls fehlend (sudo, Ubuntu/Debian)",
    )
    parser.add_argument("--no-start", action="store_true", help="Docker Compose nicht starten")
    parser.add_argument("--start", action="store_true", help="Docker Compose nach Setup starten")
    parser.add_argument("--non-interactive", action="store_true", help="Keine Prompts (Keys/Modus per Flag)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("MARIS Q/A Helper — Setup\n")

    profile = _resolve_deploy_profile(args)
    runtime = _resolve_runtime(args, profile)
    docker_status = _check_prerequisites(
        skip_docker=args.skip_docker_check,
        runtime=runtime,
        interactive=not args.non_interactive,
        auto_install_docker=args.install_docker,
    )
    lines = _ensure_env_file()

    if args.non_interactive:
        if not args.openai_key:
            raise SystemExit("--non-interactive braucht --openai-key")
        if not args.llm_auth_mode and not args.production and not args.profile:
            raise SystemExit("--non-interactive braucht --llm-auth-mode oder --profile prod")

    llm_mode = _resolve_llm_mode(args, profile)
    oauth_path = args.oauth_path.expanduser()

    if (
        args.non_interactive
        and llm_mode == "chatgpt_oauth"
        and not oauth_path.exists()
        and not args.skip_oauth_login
    ):
        raise SystemExit(
            f"OAuth-Datei fehlt: {oauth_path}\n"
            "Nutze --skip-oauth-login, login_chat_oauth.py, oder --llm-auth-mode api_key."
        )

    lines, _ = _prompt_embedding_key(
        lines,
        openai_key=args.openai_key,
        interactive=not args.non_interactive,
    )

    if llm_mode == "api_key":
        lines = _configure_chat_api_key(lines)
    else:
        lines = _configure_chat_oauth(
            lines,
            oauth_path=oauth_path,
            skip_login=args.skip_oauth_login or (args.non_interactive and not oauth_path.exists()),
        )

    lines = _configure_runtime(lines, runtime=runtime)
    lines = _configure_deploy(lines, profile=profile)
    lines = _ensure_session_secret(lines)
    _write_env(lines)

    start: bool | None = True if args.start else False if args.no_start else None
    _maybe_start_compose(
        start=start,
        runtime=runtime,
        profile=profile,
        llm_mode=llm_mode,
        oauth_path=oauth_path,
        docker_status=docker_status,
    )
    _print_next_steps(
        profile=profile,
        runtime=runtime,
        llm_mode=llm_mode,
        oauth_path=oauth_path,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nAbgebrochen.") from None
