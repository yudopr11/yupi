"""Tests for app/schemas/auth.py Pydantic schemas."""
from app.utils.uuid import uuid7
from datetime import datetime, UTC

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# UserCreate
# ---------------------------------------------------------------------------

def test_user_create_valid():
    from app.schemas.auth import UserCreate
    schema = UserCreate(username="alice", email="alice@example.com", password="secret123")
    assert schema.username == "alice"
    assert schema.email == "alice@example.com"
    assert schema.is_superuser is False


def test_user_create_superuser_flag():
    from app.schemas.auth import UserCreate
    schema = UserCreate(username="admin", email="admin@example.com", password="password123", is_superuser=True)
    assert schema.is_superuser is True


def test_user_create_missing_username_raises():
    from app.schemas.auth import UserCreate
    with pytest.raises(ValidationError):
        UserCreate(email="x@example.com", password="password123")


def test_user_create_missing_email_raises():
    from app.schemas.auth import UserCreate
    with pytest.raises(ValidationError):
        UserCreate(username="x", password="password123")


def test_user_create_invalid_email_raises():
    from app.schemas.auth import UserCreate
    with pytest.raises(ValidationError):
        UserCreate(username="x", email="not-an-email", password="password123")


def test_user_create_missing_password_raises():
    from app.schemas.auth import UserCreate
    with pytest.raises(ValidationError):
        UserCreate(username="x", email="x@example.com")


# ---------------------------------------------------------------------------
# UserResponse
# ---------------------------------------------------------------------------

def test_user_response_valid():
    from app.schemas.auth import UserResponse
    schema = UserResponse(
        id=uuid7(),
        username="bob",
        email="bob@example.com",
        is_superuser=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert schema.username == "bob"


# ---------------------------------------------------------------------------
# UserBase
# ---------------------------------------------------------------------------

def test_user_base_valid():
    from app.schemas.auth import UserBase
    schema = UserBase(username="carol", email="carol@example.com")
    assert schema.username == "carol"


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

def test_token_valid():
    from app.schemas.auth import Token
    schema = Token(access_token="abc.def.ghi", token_type="bearer")
    assert schema.access_token == "abc.def.ghi"
    assert schema.token_type == "bearer"


def test_token_missing_access_token_raises():
    from app.schemas.auth import Token
    with pytest.raises(ValidationError):
        Token(token_type="bearer")


# ---------------------------------------------------------------------------
# TokenPayload
# ---------------------------------------------------------------------------

def test_token_payload_valid():
    from app.schemas.auth import TokenPayload
    import time
    schema = TokenPayload(sub="alice", type="access", exp=int(time.time()) + 900)
    assert schema.sub == "alice"
    assert schema.type == "access"


def test_token_payload_missing_exp_raises():
    from app.schemas.auth import TokenPayload
    with pytest.raises(ValidationError):
        TokenPayload(sub="alice", type="access")


# ---------------------------------------------------------------------------
# ForgotPasswordRequest
# ---------------------------------------------------------------------------

def test_forgot_password_request_valid():
    from app.schemas.auth import ForgotPasswordRequest
    schema = ForgotPasswordRequest(email="user@example.com")
    assert schema.email == "user@example.com"


def test_forgot_password_request_invalid_email_raises():
    from app.schemas.auth import ForgotPasswordRequest
    with pytest.raises(ValidationError):
        ForgotPasswordRequest(email="not-an-email")


# ---------------------------------------------------------------------------
# ResetPasswordRequest
# ---------------------------------------------------------------------------

def test_reset_password_request_valid():
    from app.schemas.auth import ResetPasswordRequest
    schema = ResetPasswordRequest(token="some.jwt.token", new_password="newpass123")
    assert schema.token == "some.jwt.token"
    assert schema.new_password == "newpass123"


def test_reset_password_request_missing_token_raises():
    from app.schemas.auth import ResetPasswordRequest
    with pytest.raises(ValidationError):
        ResetPasswordRequest(new_password="newpass1")


# ---------------------------------------------------------------------------
# DeletedUserInfo / DeleteUserResponse
# ---------------------------------------------------------------------------

def test_deleted_user_info_valid():
    from app.schemas.auth import DeletedUserInfo
    schema = DeletedUserInfo(id=uuid7(), username="dave")
    assert schema.username == "dave"


def test_delete_user_response_valid():
    from app.schemas.auth import DeleteUserResponse, DeletedUserInfo
    schema = DeleteUserResponse(
        message="User deleted",
        deleted_item=DeletedUserInfo(id=uuid7(), username="dave")
    )
    assert schema.message == "User deleted"
    assert schema.deleted_item.username == "dave"
