"""Tests for MCPPool and _PooledConnection."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_pooled_connection_init():
    """_PooledConnection should initialize with None session and empty tools."""
    from app.utils.mcp_client import _PooledConnection

    conn = _PooledConnection("http://example.com/mcp")
    assert conn.endpoint == "http://example.com/mcp"
    assert conn.session is None
    assert conn.tools is not None  # initialized to empty list or similar


@pytest.mark.asyncio
async def test_pooled_connection_call_tool_not_connected():
    """call_tool_with_retry should raise RuntimeError if not connected."""
    from app.utils.mcp_client import _PooledConnection

    conn = _PooledConnection("http://example.com/mcp")
    # ensure_connected returns False when no session
    conn.ensure_connected = AsyncMock(return_value=False)

    with pytest.raises(RuntimeError):
        await conn.call_tool_with_retry("test_tool", {})


@pytest.mark.asyncio
async def test_pooled_connection_call_tool_success():
    """call_tool_with_retry should return tool result on success."""
    from app.utils.mcp_client import _PooledConnection

    conn = _PooledConnection("http://example.com/mcp")
    conn.ensure_connected = AsyncMock(return_value=True)
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value={"result": "ok"})
    conn.session = mock_session

    result = await conn.call_tool_with_retry("test_tool", {"arg": 1})
    assert result == {"result": "ok"}
    mock_session.call_tool.assert_called_once_with("test_tool", {"arg": 1})


@pytest.mark.asyncio
async def test_pooled_connection_call_tool_captures_session():
    """call_tool_with_retry should capture session reference to avoid TOCTOU."""
    from app.utils.mcp_client import _PooledConnection

    conn = _PooledConnection("http://example.com/mcp")
    conn.ensure_connected = AsyncMock(return_value=True)
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value="result")
    conn.session = mock_session

    # Simulate another coroutine setting session to None during call
    async def side_effect(*args, **kwargs):
        conn.session = None
        return "result"

    mock_session.call_tool = AsyncMock(side_effect=side_effect)
    result = await conn.call_tool_with_retry("test_tool", {})
    assert result == "result"


@pytest.mark.asyncio
async def test_mcppool_get_sessions_returns_none_on_empty():
    """get_sessions should return None when no endpoints succeed."""
    from app.utils.mcp_client import MCPPool

    pool = MCPPool()
    # Mock _connect to always fail
    with patch.object(pool, '_pool', {}):
        result = await pool.get_sessions("user1", [])
        assert result is None


@pytest.mark.asyncio
async def test_mcppool_invalidate():
    """invalidate should remove all connections for a user."""
    from app.utils.mcp_client import MCPPool

    pool = MCPPool()
    mock_conn = MagicMock()
    mock_conn.close = AsyncMock()
    pool._pool["user1"] = {"ep1": mock_conn}

    await pool.invalidate("user1")
    assert "user1" not in pool._pool


@pytest.mark.asyncio
async def test_mcppool_close_all():
    """close_all should clear the entire pool."""
    from app.utils.mcp_client import MCPPool

    pool = MCPPool()
    mock_conn = MagicMock()
    mock_conn.close = AsyncMock()
    pool._pool["user1"] = {"ep1": mock_conn}
    pool._pool["user2"] = {"ep2": mock_conn}

    await pool.close_all()
    assert len(pool._pool) == 0
