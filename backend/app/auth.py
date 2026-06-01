import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

_password_hasher = PasswordHasher()


class NotAuthenticatedError(Exception):
    pass


def hash_password(plaintext: str) -> str:
    return _password_hasher.hash(plaintext)


def verify_password(password_hash: str, plaintext: str) -> bool:
    try:
        _password_hasher.verify(password_hash, plaintext)
        return True
    except VerifyMismatchError:
        return False


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized = email.strip().lower()
    return db.scalar(select(User).where(User.email == normalized))


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise NotAuthenticatedError()

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        raise NotAuthenticatedError()

    return user
