from __future__ import annotations

import json
import stat
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTH_ORIGIN = "https://auth.openai.com"
DEVICE_USERCODE_URL = f"{AUTH_ORIGIN}/api/accounts/deviceauth/usercode"
DEVICE_TOKEN_URL = f"{AUTH_ORIGIN}/api/accounts/deviceauth/token"
DEVICE_VERIFY_URL = f"{AUTH_ORIGIN}/codex/device"
DEVICE_REDIRECT_URI = f"{AUTH_ORIGIN}/deviceauth/callback"
OAUTH_TOKEN_URL = f"{AUTH_ORIGIN}/oauth/token"
POLL_TIMEOUT_SECONDS = 15 * 60


def _jwt_account_id(access_token: str) -> str | None:
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(__import__("base64").urlsafe_b64decode(payload))
        auth = claims.get("https://api.openai.com/auth") or {}
        return auth.get("chatgpt_account_id") or claims.get("account_id")
    except Exception:
        return None


def _save_tokens(target: Path, token_payload: dict[str, Any]) -> None:
    access_token = token_payload["access_token"]
    out = {
        "access_token": access_token,
        "refresh_token": token_payload.get("refresh_token"),
        "id_token": token_payload.get("id_token"),
        "token_type": token_payload.get("token_type", "Bearer"),
        "scope": token_payload.get("scope"),
        "account_id": _jwt_account_id(access_token),
        "expires_at": None,  # could parse exp if wanted
        "last_refresh": time.time(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)


def start_device_flow() -> dict[str, Any]:
    """Returns info needed for user to complete device auth in browser."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            DEVICE_USERCODE_URL,
            json={"client_id": CLIENT_ID},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    if not data.get("device_auth_id") or not data.get("user_code"):
        raise RuntimeError(f"bad device response: {data}")
    return {
        "device_auth_id": data["device_auth_id"],
        "user_code": data["user_code"],
        "interval": int(data.get("interval") or 5),
        "verification_url": DEVICE_VERIFY_URL,
    }


def poll_device_completion(
    device_auth_id: str,
    user_code: str,
    interval: int,
    *,
    max_seconds: int = 25,
) -> dict[str, Any]:
    """
    Perform short polling attempts. Returns
      {"status": "pending" | "complete" | "error", "authorization_code"?, "code_verifier"?, "detail"? }
    Does not save tokens.
    """
    deadline = time.time() + max_seconds
    with httpx.Client(timeout=30.0) as client:
        while time.time() < deadline:
            try:
                resp = client.post(
                    DEVICE_TOKEN_URL,
                    json={"device_auth_id": device_auth_id, "user_code": user_code},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                if resp.status_code in (403, 404):
                    time.sleep(max(interval, 3))
                    continue
                if resp.status_code >= 400:
                    return {"status": "error", "detail": f"http_{resp.status_code}"}
                data = resp.json()
                if data.get("authorization_code") and data.get("code_verifier"):
                    return {
                        "status": "complete",
                        "authorization_code": data["authorization_code"],
                        "code_verifier": data["code_verifier"],
                    }
                time.sleep(max(interval, 3))
            except Exception as exc:
                return {"status": "error", "detail": str(exc)}
    return {"status": "pending"}


def exchange_and_save(authorization_code: str, code_verifier: str, target: Path) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
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
        resp.raise_for_status()
        tokens = resp.json()
    _save_tokens(target, tokens)
    return {"account_id": _jwt_account_id(tokens.get("access_token", ""))}


def get_oauth_target_path() -> Path:
    settings = get_settings()
    return Path(settings.codex_oauth_auth_path)
