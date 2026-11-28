import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from zxcvbn import zxcvbn

from api.auth_settings import settings


password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))

MIN_LENGTH = 8
MAX_LENGTH = 64
MIN_SCORE = 3
TOKEN_ALGORITHM = "HS256"


def validate_password(password: str) -> None:
    if not MIN_LENGTH <= len(password) <= MAX_LENGTH:
        raise ValueError("Password must contain 8-64 characters")

    if zxcvbn(password)["score"] < MIN_SCORE:
        raise ValueError("Password is too weak")


def hash_password(password: str) -> str:
    validate_password(password)
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hasher.verify(password, hashed)


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    secret_file = os.getenv("JWT_SECRET_FILE")

    if secret and secret_file:
        raise RuntimeError("Conflicting JWT secret sources")

    if secret_file:
        secret = Path(secret_file).read_text(encoding="utf-8").strip()

    if not secret or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("Missing or invalid JWT secret")

    return secret


def create_access_token(user_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.token_expiration_minutes),
    }

    return jwt.encode(
        payload, get_jwt_secret(), algorithm=TOKEN_ALGORITHM
    )

def verify_access_token(token: str) -> UUID:
    payload = jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[TOKEN_ALGORITHM],
        options={"require": ["sub", "exp"]},
    )

    return UUID(payload["sub"])


def verify_login_password(password: str, hashed: str | None) -> bool:
    valid = verify_password(password, hashed or DUMMY_HASH)
    return hashed is not None and valid
