"""TDD tests for embedded MCP server in yupi."""
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.utils.uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_token(username: str, password: str) -> str:
    return base64.b64encode(f"{username}:{password}".encode()).decode()


def make_mock_user(username="testuser", email="test@example.com", is_superuser=False):
    user = MagicMock()
    user.id = uuid7()
    user.username = username
    user.email = email
    user.is_superuser = is_superuser
    return user


# ---------------------------------------------------------------------------
# Unit tests: decode_mcp_token
# ---------------------------------------------------------------------------

def test_decode_valid_token():
    from app.mcp.server import decode_mcp_token
    token = make_token("admin", "secret")
    assert decode_mcp_token(token) == ("admin", "secret")


def test_decode_token_colon_in_password():
    from app.mcp.server import decode_mcp_token
    token = make_token("admin", "pass:word:extra")
    assert decode_mcp_token(token) == ("admin", "pass:word:extra")


def test_decode_empty_token():
    from app.mcp.server import decode_mcp_token
    assert decode_mcp_token("") is None


def test_decode_invalid_base64():
    from app.mcp.server import decode_mcp_token
    assert decode_mcp_token("not-valid-base64!!!") is None


def test_decode_no_colon():
    from app.mcp.server import decode_mcp_token
    token = base64.b64encode(b"nocolon").decode()
    assert decode_mcp_token(token) is None


# ---------------------------------------------------------------------------
# Unit tests: authenticate_for_mcp
# ---------------------------------------------------------------------------

async def test_authenticate_valid_user():
    from app.mcp.server import authenticate_for_mcp

    mock_db = MagicMock()
    mock_user = make_mock_user()
    mock_user.password = "hashed"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    with patch("app.mcp.server.verify_password", new_callable=AsyncMock, return_value=True):
        result = await authenticate_for_mcp(mock_db, "testuser", "secret")
    assert result is mock_user


async def test_authenticate_wrong_password():
    from app.mcp.server import authenticate_for_mcp

    mock_db = MagicMock()
    mock_user = make_mock_user()
    mock_user.password = "hashed"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    with patch("app.mcp.server.verify_password", new_callable=AsyncMock, return_value=False):
        result = await authenticate_for_mcp(mock_db, "testuser", "wrong")
    assert result is None


async def test_authenticate_user_not_found():
    from app.mcp.server import authenticate_for_mcp

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    result = await authenticate_for_mcp(mock_db, "ghost", "pass")
    assert result is None


# ---------------------------------------------------------------------------
# ASGI middleware tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp_asgi():
    """Create MCP ASGI app with a mock inner handler."""
    from app.mcp.server import create_mcp_asgi_app

    async def fake_inner(scope, receive, send):
        body = json.dumps({"ok": True}).encode()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})

    mock_user = make_mock_user()
    with (
        patch("app.mcp.server.SessionLocal") as mock_session_factory,
        patch("app.mcp.server.authenticate_for_mcp", new_callable=AsyncMock, return_value=mock_user),
    ):
        mock_db = MagicMock()
        mock_session_factory.return_value = mock_db
        asgi_app = create_mcp_asgi_app(fake_inner)
        yield asgi_app


@pytest.mark.asyncio
async def test_mcp_no_token_returns_401(mcp_asgi):
    async with AsyncClient(transport=ASGITransport(app=mcp_asgi), base_url="http://test") as client:
        resp = await client.post("/mcp")
        assert resp.status_code == 401
        assert "token" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_mcp_invalid_base64_returns_401(mcp_asgi):
    async with AsyncClient(transport=ASGITransport(app=mcp_asgi), base_url="http://test") as client:
        resp = await client.post("/mcp/not-base64!!!")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mcp_no_colon_token_returns_401(mcp_asgi):
    async with AsyncClient(transport=ASGITransport(app=mcp_asgi), base_url="http://test") as client:
        token = base64.b64encode(b"nocolon").decode()
        resp = await client.post(f"/mcp/{token}")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mcp_invalid_credentials_returns_401():
    from app.mcp.server import create_mcp_asgi_app

    async def fake_inner(scope, receive, send):
        pass

    with (
        patch("app.mcp.server.SessionLocal") as mock_session_factory,
        patch("app.mcp.server.authenticate_for_mcp", new_callable=AsyncMock, return_value=None),
    ):
        mock_session_factory.return_value = MagicMock()
        app = create_mcp_asgi_app(fake_inner)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = make_token("bad", "creds")
            resp = await client.post(f"/mcp/{token}")
        assert resp.status_code == 401
        assert "invalid" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_mcp_valid_token_passes_to_inner():
    from app.mcp.server import create_mcp_asgi_app

    inner_called = []

    async def recording_inner(scope, receive, send):
        inner_called.append(scope["path"])
        body = b"{}"
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-length", b"2")]})
        await send({"type": "http.response.body", "body": body})

    mock_user = make_mock_user()
    with (
        patch("app.mcp.server.SessionLocal") as mock_session_factory,
        patch("app.mcp.server.authenticate_for_mcp", new_callable=AsyncMock, return_value=mock_user),
    ):
        mock_session_factory.return_value = MagicMock()
        app = create_mcp_asgi_app(recording_inner)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = make_token("admin", "pass")
            await client.post(f"/mcp/{token}")

    assert len(inner_called) == 1
    assert inner_called[0] == "/mcp"


# ---------------------------------------------------------------------------
# Tool unit tests (context var injection)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_get_current_user():
    from app.mcp.context import _current_user_var
    from app.mcp.tools import get_current_user_impl

    user = make_mock_user(username="alice", email="alice@example.com")
    tok = _current_user_var.set(user)
    try:
        result = await get_current_user_impl()
        assert result["username"] == "alice"
        assert result["email"] == "alice@example.com"
        assert result["is_superuser"] is False
    finally:
        _current_user_var.reset(tok)


@pytest.mark.asyncio
async def test_tool_list_all_users_superuser():
    from app.mcp.context import _current_user_var, _current_db_var
    from app.mcp.tools import list_all_users_impl

    superuser = make_mock_user(is_superuser=True)

    u1 = MagicMock()
    u1.id = uuid7()
    u1.username = "bob"
    u1.email = "bob@example.com"
    u1.is_superuser = False
    u1.created_at = None
    u1.updated_at = None

    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.all.return_value = [u1]

    t1 = _current_user_var.set(superuser)
    t2 = _current_db_var.set(mock_db)
    try:
        result = await list_all_users_impl()
        assert isinstance(result, list)
        assert result[0]["username"] == "bob"
    finally:
        _current_user_var.reset(t1)
        _current_db_var.reset(t2)


@pytest.mark.asyncio
async def test_tool_list_all_users_non_superuser_raises():
    from app.mcp.context import _current_user_var, _current_db_var
    from app.mcp.tools import list_all_users_impl

    regular = make_mock_user(is_superuser=False)
    mock_db = MagicMock()

    t1 = _current_user_var.set(regular)
    t2 = _current_db_var.set(mock_db)
    try:
        with pytest.raises(PermissionError):
            await list_all_users_impl()
    finally:
        _current_user_var.reset(t1)
        _current_db_var.reset(t2)


@pytest.mark.asyncio
async def test_tool_list_accounts_calls_db():
    from app.mcp.context import _current_user_var, _current_db_var
    from app.mcp.tools import list_accounts_impl

    user = make_mock_user()
    mock_db = MagicMock()

    t1 = _current_user_var.set(user)
    t2 = _current_db_var.set(mock_db)
    try:
        with patch("app.mcp.tools.get_accounts_with_balance", return_value=[]) as mock_fn:
            result = await list_accounts_impl()
            mock_fn.assert_called_once_with(mock_db, user.id, None, as_of=None)
            assert result == []
    finally:
        _current_user_var.reset(t1)
        _current_db_var.reset(t2)


@pytest.mark.asyncio
async def test_tool_list_categories_calls_db():
    from app.mcp.context import _current_user_var, _current_db_var
    from app.mcp.tools import list_categories_impl

    user = make_mock_user()
    mock_db = MagicMock()

    cat = MagicMock()
    cat.id = uuid7()
    cat.name = "Food"
    cat.type = MagicMock()
    cat.type.value = "expense"
    cat.user_id = user.id
    cat.created_at = None
    cat.updated_at = None

    t1 = _current_user_var.set(user)
    t2 = _current_db_var.set(mock_db)
    try:
        with patch("app.mcp.tools.get_filtered_categories", return_value=[cat]):
            result = await list_categories_impl()
            assert len(result) == 1
            assert result[0]["name"] == "Food"
    finally:
        _current_user_var.reset(t1)
        _current_db_var.reset(t2)


@pytest.mark.asyncio
async def test_tool_list_transactions_calls_db():
    from app.mcp.context import _current_user_var, _current_db_var
    from app.mcp.tools import list_transactions_impl

    user = make_mock_user()
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.count.return_value = 0
    mock_query.offset.return_value.limit.return_value.all.return_value = []

    t1 = _current_user_var.set(user)
    t2 = _current_db_var.set(mock_db)
    try:
        with patch("app.mcp.tools.get_filtered_transactions", return_value=mock_query):
            result = await list_transactions_impl()
            assert result["total_count"] == 0
            assert result["data"] == []
    finally:
        _current_user_var.reset(t1)
        _current_db_var.reset(t2)
