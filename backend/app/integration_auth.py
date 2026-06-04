from __future__ import annotations

import secrets

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.auth import get_user_by_email
from app.config import get_settings
from app.db import get_db
from app.models import User


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
    settings = get_settings()
    if not settings.integration_enabled:
        raise IntegrationDisabledError()

    token = _extract_bearer_token(authorization)
    if not token:
        raise InvalidIntegrationTokenError()

    expected = settings.INTEGRATION_API_TOKEN.strip()
    if not secrets.compare_digest(token, expected):
        raise InvalidIntegrationTokenError()

    user = get_user_by_email(db, settings.INTEGRATION_USER_EMAIL)
    if user is None or not user.is_active:
        raise IntegrationUserNotFoundError()

    return user
