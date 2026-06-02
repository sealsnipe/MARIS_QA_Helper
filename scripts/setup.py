#!/usr/bin/env python3
"""Interactive first-time setup: prerequisites, .env, embeddings key, chat auth (API or OAuth)."""

from __future__ import annotations

import argparse
import getpass
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"
DEFAULT_OAUTH_PATH = Path.home() / ".oauth_codex" / "auth.json"

PLACEHOLDER_KEY = "sk-placeholder-replace-me"
KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{10,}$")

CHAT_MODEL_API = "gpt-4.1-mini"
CHAT_MODEL_OAUTH = "gpt-5.4-mini"


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


def _check_prerequisites(*, skip_docker: bool) -> None:
    print("\n=== Voraussetzungen ===\n")
    py = sys.version_info
    if py < (3, 12):
        print(f"  ⚠ Python {py.major}.{py.minor} — empfohlen: 3.12+")
    else:
        print(f"  ✓ Python {py.major}.{py.minor}")

    if skip_docker:
        print("  ○ Docker-Check übersprungen")
        return

    if shutil.which("docker"):
        print("  ✓ docker")
    else:
        print("  ⚠ docker nicht gefunden (für Compose-Start nötig)")

    compose_ok = False
    if shutil.which("docker"):
        for cmd in (["docker", "compose", "version"], ["docker-compose", "version"]):
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                compose_ok = True
                print(f"  ✓ {' '.join(cmd[:2])}")
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    if not compose_ok:
        print("  ⚠ docker compose nicht gefunden")


def _ensure_env_file() -> list[str]:
    if ENV_PATH.exists():
        print(f"\n  Vorhandene {ENV_PATH.name} wird aktualisiert.")
        return _read_lines(ENV_PATH)
    if not EXAMPLE_PATH.exists():
        raise SystemExit(f"Fehlt: {EXAMPLE_PATH}")
    shutil.copy(EXAMPLE_PATH, ENV_PATH)
    print(f"\n  {EXAMPLE_PATH.name} → {ENV_PATH.name}")
    return _read_lines(ENV_PATH)


def _prompt_embedding_key(lines: list[str], *, openai_key: str | None) -> tuple[list[str], str]:
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
            print(f"  ⚠ Keine OAuth-Datei unter {oauth_path} — später: python3 scripts/login_chat_oauth.py")
        return lines

    if oauth_path.exists() and _prompt_yes_no(f"Vorhandene OAuth-Session behalten ({oauth_path})?", default=True):
        return lines

    # Import login flow from sibling script (same repo, no package install needed).
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


def _ensure_session_secret(lines: list[str]) -> list[str]:
    current = _get_value(lines, "SESSION_SECRET")
    weak = not current or "change-me" in current or len(current) < 32
    if weak:
        lines = _upsert(lines, "SESSION_SECRET", secrets.token_urlsafe(48))
        print("\n  SESSION_SECRET generiert.")
    return lines


def _maybe_start_compose(*, start: bool | None) -> None:
    if start is False:
        return
    if start is None and not _prompt_yes_no("\nDocker Compose jetzt starten (api + qdrant)?", default=True):
        return

    if not shutil.which("docker"):
        print("  Docker nicht installiert — übersprungen.")
        return

    print("\n=== Docker Compose ===\n")
    cmd = ["docker", "compose", "up", "--build", "-d"]
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
    except subprocess.CalledProcessError:
        print("  docker compose fehlgeschlagen. Manuell: docker compose up --build")
        return

    print("  ✓ Stack gestartet — http://127.0.0.1:8088")
    print("  Health: curl http://127.0.0.1:8088/api/health")


def _print_next_steps(llm_mode: str) -> None:
    print("\n=== Fertig ===\n")
    print("Nächste Schritte:")
    print("  • Seed (Demo):  docker compose exec api python scripts/seed_data.py")
    print("  • Dev lokal:    cd backend && uvicorn app.main:app --reload --port 8088")
    if llm_mode == "chatgpt_oauth":
        print("  • OAuth-Test:   python3 scripts/smoke_chat_oauth.py")
    else:
        print("  • API-Test:     python3 scripts/smoke_openai.py")
    print("  • Env prüfen:   python3 scripts/setup_env.py --check-only")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MARIS Q/A Helper — interaktives Erst-Setup (.env + Chat-Auth)",
    )
    parser.add_argument("--openai-key", help="OpenAI API-Key (Embeddings); sonst interaktiv")
    parser.add_argument(
        "--llm-auth-mode",
        choices=("api_key", "chatgpt_oauth"),
        help="Chat-Authentifizierung (sonst interaktive Auswahl)",
    )
    parser.add_argument(
        "--oauth-path",
        type=Path,
        default=DEFAULT_OAUTH_PATH,
        help=f"Ziel für OAuth-Tokens (Default: {DEFAULT_OAUTH_PATH})",
    )
    parser.add_argument("--skip-oauth-login", action="store_true", help="OAuth nur in .env eintragen")
    parser.add_argument("--skip-docker-check", action="store_true")
    parser.add_argument("--no-start", action="store_true", help="Docker Compose nicht starten")
    parser.add_argument("--start", action="store_true", help="Docker Compose nach Setup starten")
    parser.add_argument("--non-interactive", action="store_true", help="Keine Prompts (Keys/Modus per Flag)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("MARIS Q/A Helper — Setup\n")

    _check_prerequisites(skip_docker=args.skip_docker_check)
    lines = _ensure_env_file()

    if args.non_interactive:
        if not args.openai_key and not args.llm_auth_mode:
            raise SystemExit("--non-interactive braucht --openai-key und --llm-auth-mode")
        llm_mode = args.llm_auth_mode
    else:
        llm_mode = args.llm_auth_mode or _prompt_choice(
            "\nWie soll der Chat-Agent authentifizieren?",
            [
                ("chatgpt_oauth", "ChatGPT OAuth — Browser-Login (Codex/Plus-Abo, Dev/WSL)"),
                ("api_key", "OpenAI API-Key — Platform-Billing (Produktion/Docker)"),
            ],
        )

    lines, _ = _prompt_embedding_key(lines, openai_key=args.openai_key)

    if llm_mode == "api_key":
        lines = _configure_chat_api_key(lines)
    else:
        lines = _configure_chat_oauth(
            lines,
            oauth_path=args.oauth_path.expanduser(),
            skip_login=args.skip_oauth_login or args.non_interactive,
        )

    lines = _ensure_session_secret(lines)
    _write_env(lines)

    start: bool | None = True if args.start else False if args.no_start else None
    _maybe_start_compose(start=start)
    _print_next_steps(llm_mode)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nAbgebrochen.") from None
