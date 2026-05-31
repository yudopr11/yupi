"""Tests for app/utils/auth.py — password, JWT, and user dependency helpers."""
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# verify_password / get_password_hash
# ---------------------------------------------------------------------------

async def test_get_password_hash_produces_bcrypt_hash():
    from app.utils.auth import get_password_hash
    hashed = await get_password_hash("mysecret")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


async def test_verify_password_correct():
    from app.utils.auth import get_password_hash, verify_password
    hashed = await get_password_hash("correct")
    assert await verify_password("correct", hashed) is True


async def test_verify_password_wrong():
    from app.utils.auth import get_password_hash, verify_password
    hashed = await get_password_hash("correct")
    assert await verify_password("wrong", hashed) is False


async def test_verify_password_empty_plain():
    from app.utils.auth import get_password_hash, verify_password
    hashed = await get_password_hash("nonempty")
    assert await verify_password("", hashed) is False


# ---------------------------------------------------------------------------
# create_token / verify_token
# ---------------------------------------------------------------------------

def test_create_token_returns_string():
    from app.utils.auth import create_token
    token = create_token({"sub": "alice"}, timedelta(minutes=15), "access")
    assert isinstance(token, str)
    assert len(token) > 10


def test_verify_token_access_valid():
    from app.utils.auth import create_token, verify_token
    token = create_token({"sub": "alice"}, timedelta(minutes=15), "access")
    payload = verify_token(token, "access")
    assert payload.sub == "alice"
    assert payload.type == "access"


def test_verify_token_refresh_valid():
    from app.utils.auth import create_token, verify_token
    token = create_token({"sub": "bob"}, timedelta(days=7), "refresh")
    payload = verify_token(token, "refresh")
    assert payload.sub == "bob"
    assert payload.type == "refresh"


def test_verify_token_wrong_type_raises_401():
    from app.utils.auth import create_token, verify_token
    token = create_token({"sub": "alice"}, timedelta(minutes=15), "access")
    with pytest.raises(HTTPException) as exc:
        verify_token(token, "refresh")
    assert exc.value.status_code == 401


def test_verify_token_expired_raises_401():
    from app.utils.auth import create_token, verify_token
    token = create_token({"sub": "alice"}, timedelta(seconds=-1), "access")
    with pytest.raises(HTTPException) as exc:
        verify_token(token, "access")
    assert exc.value.status_code == 401


def test_verify_token_garbage_raises_401():
    from app.utils.auth import verify_token
    with pytest.raises(HTTPException) as exc:
        verify_token("not.a.jwt", "access")
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# create_tokens
# ---------------------------------------------------------------------------

def test_create_tokens_returns_two_distinct_strings():
    from app.utils.auth import create_tokens, verify_token
    access, refresh = create_tokens("charlie")
    assert access != refresh
    a = verify_token(access, "access")
    r = verify_token(refresh, "refresh")
    assert a.sub == "charlie"
    assert r.sub == "charlie"


# ---------------------------------------------------------------------------
# create_password_reset_token
# ---------------------------------------------------------------------------

def test_create_password_reset_token_type_is_reset():
    from app.utils.auth import create_password_reset_token, verify_token
    token = create_password_reset_token("user@example.com")
    payload = verify_token(token, "reset")
    assert payload.sub == "user@example.com"
    assert payload.type == "reset"


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_user_returns_user():
    from app.utils.auth import create_token, get_current_user
    from app.models.auth import User

    token = create_token({"sub": "dave"}, timedelta(minutes=15), "access")
    mock_user = MagicMock(spec=User)
    mock_user.username = "dave"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    result = await get_current_user(token=token, db=mock_db)
    assert result is mock_user


@pytest.mark.asyncio
async def test_get_current_user_unknown_user_raises_401():
    from app.utils.auth import create_token, get_current_user

    token = create_token({"sub": "ghost"}, timedelta(minutes=15), "access")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=mock_db)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_superuser dependency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_superuser_ok():
    from app.utils.auth import get_current_superuser
    from app.models.auth import User

    mock_user = MagicMock(spec=User)
    mock_user.is_superuser = True

    result = await get_current_superuser(current_user=mock_user)
    assert result is mock_user


@pytest.mark.asyncio
async def test_get_current_superuser_non_superuser_raises_403():
    from app.utils.auth import get_current_superuser
    from app.models.auth import User

    mock_user = MagicMock(spec=User)
    mock_user.is_superuser = False

    with pytest.raises(HTTPException) as exc:
        await get_current_superuser(current_user=mock_user)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# get_non_guest_user dependency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_non_guest_user_ok():
    from app.utils.auth import get_non_guest_user
    from app.models.auth import User

    mock_user = MagicMock(spec=User)
    mock_user.username = "alice"

    result = await get_non_guest_user(current_user=mock_user)
    assert result is mock_user


@pytest.mark.asyncio
async def test_get_non_guest_user_guest_raises_403():
    from app.utils.auth import get_non_guest_user
    from app.models.auth import User

    mock_user = MagicMock(spec=User)
    mock_user.username = "guest"

    with pytest.raises(HTTPException) as exc:
        await get_non_guest_user(current_user=mock_user)
    assert exc.value.status_code == 403
