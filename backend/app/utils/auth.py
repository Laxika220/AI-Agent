"""Password hashing (bcrypt) and JWT encode/decode."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt

from app.config import get_settings
from app.core.errors import AuthenticationError

TokenType = Literal["access", "refresh"]

# bcrypt only uses the first 72 bytes; truncate explicitly so behaviour is defined.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_BCRYPT_MAX_BYTES], hashed.encode("utf-8"))
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class TokenPayload:
    sub: str
    type: TokenType
    jti: str
    exp: datetime


def _create_token(subject: str, token_type: TokenType, lifetime: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    minutes = get_settings().access_token_expire_minutes
    return _create_token(user_id, "access", timedelta(minutes=minutes))


def create_refresh_token(user_id: str) -> str:
    days = get_settings().refresh_token_expire_days
    return _create_token(user_id, "refresh", timedelta(days=days))


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    """Validate signature, expiry and token type.

    Raises:
        AuthenticationError: if the token is invalid for any reason.
    """
    settings = get_settings()
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "jti", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token") from exc

    if data.get("type") != expected_type:
        raise AuthenticationError(f"Expected a {expected_type} token")
    return TokenPayload(
        sub=str(data["sub"]),
        type=data["type"],
        jti=str(data["jti"]),
        exp=datetime.fromtimestamp(int(data["exp"]), tz=UTC),
    )
