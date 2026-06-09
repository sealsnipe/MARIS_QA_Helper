from __future__ import annotations

import secrets

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.auth import get_user_by_email
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.secrets_admin import get_effective_secret


class IntegrationDisabledError(Exception):
    pass


class InvalidIntegrationTokenError(Exception):
    pass


class IntegrationUserNotFoundError(Exception):
    pass


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


async def get_integration_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """Authenticates integration requests using the effective token (DB override via
    update_secret takes precedence over ENV/settings; empty DB value disables even if ENV set).
    Source of truth for the token secret: DB (AppSecret) with ENV fallback.
    """
    # Enabled / token from effective secret (DB first, then settings fallback)
    expected = get_effective_secret(db, "integration_api_token") or ""
    if not expected.strip():
        raise IntegrationDisabledError()

    token = _extract_bearer_token(authorization)
    if not token:
        raise InvalidIntegrationTokenError()

    if not secrets.compare_digest(token, expected.strip()):
        raise InvalidIntegrationTokenError()

    # User lookup still via settings (INTEGRATION_USER_EMAIL); token is the varying secret
    settings = get_settings()
    user = get_user_by_email(db, settings.INTEGRATION_USER_EMAIL)
    if user is None or not user.is_active:
        raise IntegrationUserNotFoundError()

    return user
