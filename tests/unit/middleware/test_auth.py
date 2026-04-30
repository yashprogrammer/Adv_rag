"""Unit tests for JWT auth middleware."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.middleware.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)


def _cred(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self) -> None:
        plain = "supersecret"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_fails(self) -> None:
        plain = "supersecret"
        hashed = hash_password(plain)
        assert verify_password("wrong", hashed) is False


class TestJWT:
    def test_create_and_decode_roundtrip(self) -> None:
        token = create_access_token("alice")
        user = get_current_user(_cred(token))
        assert user.username == "alice"
        assert user.is_admin is False

    def test_expired_token_rejected(self) -> None:
        token = create_access_token("alice", expires_delta_seconds=-1)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(_cred(token))
        assert exc_info.value.status_code == 401

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token("alice")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(_cred(tampered))
        assert exc_info.value.status_code == 401

    def test_malformed_token_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(_cred("not.a.token"))
        assert exc_info.value.status_code == 401
