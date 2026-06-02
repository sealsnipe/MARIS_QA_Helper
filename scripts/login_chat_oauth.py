#!/usr/bin/env python3
"""ChatGPT OAuth login for Ubuntu/WSL (device code). Saves to ~/.oauth_codex/auth.json."""

from __future__ import annotations

import argparse
import base64
import json
import stat
import sys
import time
from pathlib import Path

import httpx

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTH_ORIGIN = "https://auth.openai.com"
DEVICE_USERCODE_URL = f"{AUTH_ORIGIN}/api/accounts/deviceauth/usercode"
DEVICE_TOKEN_URL = f"{AUTH_ORIGIN}/api/accounts/deviceauth/token"
DEVICE_VERIFY_URL = f"{AUTH_ORIGIN}/codex/device"
DEVICE_REDIRECT_URI = f"{AUTH_ORIGIN}/deviceauth/callback"
OAUTH_TOKEN_URL = f"{AUTH_ORIGIN}/oauth/token"
DEFAULT_TARGET = Path.home() / ".oauth_codex" / "auth.json"
POLL_TIMEOUT_SECONDS = 15 * 60


def _jwt_account_id(access_token: str) -> str | None:
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        auth = claims.get("https://api.openai.com/auth") or {}
        return auth.get("chatgpt_account_id") or claims.get("account_id")
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def _jwt_expires_at(access_token: str) -> float | None:
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        exp = claims.get("exp")
        return float(exp) if exp is not None else None
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def _save_tokens(target: Path, token_payload: dict) -> None:
    access_token = token_payload["access_token"]
    out = {
        "access_token": access_token,
        "refresh_token": token_payload.get("refresh_token"),
        "id_token": token_payload.get("id_token"),
        "token_type": token_payload.get("token_type", "Bearer"),
        "scope": token_payload.get("scope"),
        "account_id": _jwt_account_id(access_token),
        "expires_at": _jwt_expires_at(access_token),
        "last_refresh": time.time(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"\nSaved OAuth tokens to {target}")
    if out.get("account_id"):
        print(f"ChatGPT account_id: {out['account_id']}")


def _create_device_session(client: httpx.Client) -> dict:
    response = client.post(
        DEVICE_USERCODE_URL,
        json={"client_id": CLIENT_ID},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    response.raise_for_status()
    data = response.json()
    required = ("device_auth_id", "user_code")
    if not all(data.get(key) for key in required):
        raise RuntimeError(f"Unexpected device-code response: {data}")
    return data


def _poll_device_token(client: httpx.Client, device_auth_id: str, user_code: str, interval: int) -> dict:
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        response = client.post(
            DEVICE_TOKEN_URL,
            json={"device_auth_id": device_auth_id, "user_code": user_code},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if response.status_code in {403, 404}:
            time.sleep(max(interval, 3))
            continue
        if response.status_code >= 400:
            raise RuntimeError(f"Device auth poll failed ({response.status_code}): {response.text}")

        data = response.json()
        if data.get("authorization_code") and data.get("code_verifier"):
            return data
        time.sleep(max(interval, 3))

    raise TimeoutError("Device auth timed out after 15 minutes. Run the script again.")


def _exchange_code(client: httpx.Client, authorization_code: str, code_verifier: str) -> dict:
    response = client.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": DEVICE_REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": code_verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def login_device_code(target: Path) -> None:
    print("ChatGPT OAuth login (Ubuntu/WSL, device code)")
    print("Tokens werden NUR im Linux-Dateisystem gespeichert.\n")

    with httpx.Client(timeout=60.0) as client:
        session = _create_device_session(client)
        device_auth_id = session["device_auth_id"]
        user_code = session["user_code"]
        interval = int(session.get("interval") or 5)

        print("1) Browser öffnen:")
        print(f"   {DEVICE_VERIFY_URL}")
        print("2) Einmalcode eingeben:")
        print(f"   {user_code}")
        print("\nWarte auf Bestätigung im Browser ...")

        polled = _poll_device_token(client, device_auth_id, user_code, interval)
        tokens = _exchange_code(
            client,
            authorization_code=polled["authorization_code"],
            code_verifier=polled["code_verifier"],
        )

    _save_tokens(target, tokens)
    print("\nFertig. Test:")
    print("  python3 scripts/smoke_chat_oauth.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Login ChatGPT OAuth in Ubuntu (device code)")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="Output auth file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        login_device_code(args.target.expanduser())
    except KeyboardInterrupt:
        raise SystemExit("\nAbgebrochen.") from None
    except Exception as exc:
        raise SystemExit(f"Login fehlgeschlagen: {exc}") from exc


if __name__ == "__main__":
    main()
