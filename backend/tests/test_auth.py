import pytest

from app.core.errors import AuthenticationError
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_roundtrip() -> None:
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_and_refresh_tokens_are_typed() -> None:
    access = create_access_token("user-1")
    refresh = create_refresh_token("user-1")
    assert decode_token(access, "access").sub == "user-1"
    assert decode_token(refresh, "refresh").sub == "user-1"
    with pytest.raises(AuthenticationError):
        decode_token(access, "refresh")
    with pytest.raises(AuthenticationError):
        decode_token(refresh, "access")


def test_tampered_token_is_rejected() -> None:
    token = create_access_token("user-1")
    with pytest.raises(AuthenticationError):
        decode_token(token[:-2] + "xx", "access")
