from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.oauth_token_store import save_oauth_tokens, load_oauth_tokens, touch_token_refresh

XAI_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
XAI_SCOPE = "openid profile email offline_access grok-cli:access api:access"
XAI_DEVICE_URL = "https://auth.x.ai/oauth2/device/code"
XAI_TOKEN_URL = "https://auth.x.ai/oauth2/token"
DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


def _jwt_claim(token: str, *keys: str) -> str | None:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        for key in keys:
            if key in claims and claims[key]:
                return str(claims[key])
        return None
    except Exception:
        return None


def _account_label(access_token: str, id_token: str | None = None) -> str | None:
    for token in (id_token, access_token):
        if not token:
            continue
        for key in ("email", "preferred_username", "sub", "name"):
            val = _jwt_claim(token, key)
            if val:
                return val
    return None


def _expires_at(payload: dict[str, Any]) -> float | None:
    exp = payload.get("expires_in")
    if exp is None:
        return payload.get("expires_at")
    try:
        return time.time() + float(exp)
    except (TypeError, ValueError):
        return None


def _normalize_token_payload(raw: dict[str, Any]) -> dict[str, Any]:
    access = raw.get("access_token") or ""
    id_token = raw.get("id_token")
    return {
        "provider": "grok",
        "access_token": access,
        "refresh_token": raw.get("refresh_token"),
        "id_token": id_token,
        "token_type": raw.get("token_type", "Bearer"),
        "scope": raw.get("scope"),
        "account_label": _account_label(access, id_token),
        "expires_at": _expires_at(raw),
        "last_refresh": time.time(),
    }


def start_device_flow() -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            XAI_DEVICE_URL,
            data={"client_id": XAI_CLIENT_ID, "scope": XAI_SCOPE},
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    device_code = data.get("device_code")
    user_code = data.get("user_code")
    if not device_code or not user_code:
        raise RuntimeError(f"bad xai device response: {data}")
    return {
        "provider": "grok",
        "device_code": device_code,
        "user_code": user_code,
        "interval": int(data.get("interval") or 5),
        "verification_url": data.get("verification_uri_complete") or data.get("verification_uri") or "",
        "expires_in": int(data.get("expires_in") or 600),
    }


def poll_device_completion(device_code: str, interval: int, *, max_seconds: int = 25) -> dict[str, Any]:
    deadline = time.time() + max_seconds
    with httpx.Client(timeout=30.0) as client:
        while time.time() < deadline:
            resp = client.post(
                XAI_TOKEN_URL,
                data={
                    "grant_type": DEVICE_CODE_GRANT,
                    "device_code": device_code,
                    "client_id": XAI_CLIENT_ID,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            )
            if resp.status_code >= 500:
                time.sleep(max(interval, 3))
                continue
            try:
                data = resp.json()
            except Exception:
                return {"status": "error", "detail": f"http_{resp.status_code}"}

            err = data.get("error")
            if err in {"authorization_pending", "slow_down"}:
                wait = int(data.get("interval") or interval or 5)
                if err == "slow_down":
                    wait = max(wait + 2, 5)
                time.sleep(wait)
                continue
            if err:
                return {"status": "error", "detail": err}

            if data.get("access_token"):
                return {"status": "complete", "tokens": data}
            time.sleep(max(interval, 3))
    return {"status": "pending"}


def exchange_and_save(tokens: dict[str, Any], target: Path) -> dict[str, Any]:
    normalized = _normalize_token_payload(tokens)
    save_oauth_tokens(target, normalized)
    return {"account_label": normalized.get("account_label")}


def refresh_access_token(target: Path) -> str:
    data = load_oauth_tokens(target)
    access = (data.get("access_token") or "").strip()
    expires_at = data.get("expires_at")
    if access and expires_at and time.time() < float(expires_at) - 60:
        return access

    refresh = (data.get("refresh_token") or "").strip()
    if not refresh:
        raise RuntimeError("xai_oauth_missing_refresh_token")

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            XAI_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": XAI_CLIENT_ID,
                "refresh_token": refresh,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        resp.raise_for_status()
        payload = resp.json()

    merged = {**data, **_normalize_token_payload({**payload, "refresh_token": payload.get("refresh_token") or refresh})}
    touch_token_refresh(target, merged)
    token = (merged.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("xai_oauth_refresh_empty")
    return token


def auth_headers(target: Path) -> dict[str, str]:
    token = refresh_access_token(target)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
