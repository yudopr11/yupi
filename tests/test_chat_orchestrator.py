"""Tests for app/services/chat_orchestrator.py."""
import json
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# _build_local_tool_definitions
# ---------------------------------------------------------------------------

def test_build_local_tool_definitions_basic():
    """Tools from MCP server get converted to Anthropic format."""
    from app.utils.chat_orchestrator import _build_local_tool_definitions

    mock_fn = MagicMock()
    mock_fn.__doc__ = "List all accounts"
    mock_fn.__annotations__ = {"limit": int, "return": list}
    mock_fn.__signature__ = None

    import inspect
    mock_fn.__signature__ = inspect.Signature([
        inspect.Parameter("limit", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=10, annotation=int),
    ])

    mock_tool = MagicMock()
    mock_tool.fn = mock_fn

    mock_manager = MagicMock()
    mock_manager._tools = {"list_accounts": mock_tool}

    with patch("app.utils.chat_orchestrator.mcp_server") as mock_server:
        mock_server._tool_manager = mock_manager
        tools = _build_local_tool_definitions()

    assert len(tools) == 1
    t = tools[0]
    assert t["name"] == "list_accounts"
    assert t["description"] == "List all accounts"
    assert t["input_schema"]["type"] == "object"
    assert "limit" in t["input_schema"]["properties"]
    assert t["input_schema"]["properties"]["limit"]["type"] == "integer"
    # limit has default, so not required
    assert "limit" not in t["input_schema"].get("required", [])


def test_build_local_tool_definitions_required_param():
    """Params without defaults are marked required."""
    import inspect
    from app.utils.chat_orchestrator import _build_local_tool_definitions

    mock_fn = MagicMock()
    mock_fn.__doc__ = "Search"
    mock_fn.__annotations__ = {"query": str, "return": list}
    mock_fn.__signature__ = inspect.Signature([
        inspect.Parameter("query", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
    ])

    mock_tool = MagicMock()
    mock_tool.fn = mock_fn

    with patch("app.utils.chat_orchestrator.mcp_server") as mock_server:
        mock_server._tool_manager._tools = {"search": mock_tool}
        tools = _build_local_tool_definitions()

    assert "query" in tools[0]["input_schema"]["required"]


def test_build_local_tool_definitions_type_mapping():
    """All Python types map to correct JSON Schema types."""
    import inspect
    from app.utils.chat_orchestrator import _build_local_tool_definitions

    params = [
        inspect.Parameter("s", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
        inspect.Parameter("i", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
        inspect.Parameter("f", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=float),
        inspect.Parameter("b", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=bool),
        inspect.Parameter("ls", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=list[str]),
        inspect.Parameter("d", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=dict),
        inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=object),
    ]

    mock_fn = MagicMock()
    mock_fn.__doc__ = "Test tool"
    mock_fn.__annotations__ = {p.name: p.annotation for p in params}
    mock_fn.__annotations__["return"] = None
    mock_fn.__signature__ = inspect.Signature(params)

    mock_tool = MagicMock()
    mock_tool.fn = mock_fn

    with patch("app.utils.chat_orchestrator.mcp_server") as mock_server:
        mock_server._tool_manager._tools = {"test": mock_tool}
        tools = _build_local_tool_definitions()

    props = tools[0]["input_schema"]["properties"]
    assert props["s"]["type"] == "string"
    assert props["i"]["type"] == "integer"
    assert props["f"]["type"] == "number"
    assert props["b"]["type"] == "boolean"
    assert props["ls"]["type"] == "array"
    assert props["ls"]["items"] == {"type": "string"}
    assert props["d"]["type"] == "object"
    assert props["x"]["type"] == "string"  # fallback


# ---------------------------------------------------------------------------
# _execute_tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_tool_success():
    """Tool execution sets context vars and returns JSON result."""
    from app.utils.chat_orchestrator import _execute_local_tool

    mock_fn = AsyncMock(return_value={"accounts": []})
    mock_tool = MagicMock()
    mock_tool.fn = mock_fn

    mock_user = MagicMock()
    mock_db = MagicMock()

    with patch("app.utils.chat_orchestrator.mcp_server") as mock_server, \
         patch("app.utils.chat_orchestrator._current_user_var") as mock_user_var, \
         patch("app.utils.chat_orchestrator._current_db_var") as mock_db_var:
        mock_server._tool_manager._tools = {"list_accounts": mock_tool}
        mock_user_var.set = MagicMock(return_value="token_u")
        mock_user_var.reset = MagicMock()
        mock_db_var.set = MagicMock(return_value="token_d")
        mock_db_var.reset = MagicMock()

        result = await _execute_local_tool("list_accounts", {"limit": 5}, mock_user, mock_db)

    data = json.loads(result)
    assert data == {"accounts": []}
    mock_fn.assert_awaited_once_with(limit=5)


@pytest.mark.asyncio
async def test_execute_tool_unknown_tool():
    """Unknown tool name returns error JSON."""
    from app.utils.chat_orchestrator import _execute_local_tool

    with patch("app.utils.chat_orchestrator.mcp_server") as mock_server:
        mock_server._tool_manager._tools = {}
        result = await _execute_local_tool("nonexistent", {}, MagicMock(), MagicMock())

    data = json.loads(result)
    assert "error" in data
    assert "Unknown tool" in data["error"]


@pytest.mark.asyncio
async def test_execute_tool_exception():
    """Tool raising exception returns error JSON."""
    from app.utils.chat_orchestrator import _execute_local_tool

    mock_fn = AsyncMock(side_effect=ValueError("boom"))
    mock_tool = MagicMock()
    mock_tool.fn = mock_fn

    with patch("app.utils.chat_orchestrator.mcp_server") as mock_server, \
         patch("app.utils.chat_orchestrator._current_user_var") as mock_uv, \
         patch("app.utils.chat_orchestrator._current_db_var") as mock_dv:
        mock_server._tool_manager._tools = {"bad_tool": mock_tool}
        mock_uv.set = MagicMock(return_value="t")
        mock_uv.reset = MagicMock()
        mock_dv.set = MagicMock(return_value="t")
        mock_dv.reset = MagicMock()

        result = await _execute_local_tool("bad_tool", {}, MagicMock(), MagicMock())

    data = json.loads(result)
    assert "boom" in data["error"]


# ---------------------------------------------------------------------------
# run_chat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_chat_text_only():
    """LLM returns text only — yields text + done events."""
    from app.utils.chat_orchestrator import run_chat

    # Mock streaming events
    text_event = MagicMock()
    text_event.type = "content_block_delta"
    text_event.delta.type = "text_delta"
    text_event.delta.text = "Hello!"

    block_start = MagicMock()
    block_start.type = "content_block_start"
    block_start.content_block.type = "text"

    block_stop = MagicMock()
    block_stop.type = "content_block_stop"

    class MockAsyncIterator:
        def __init__(self, items):
            self._iter = iter(items)
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=MockAsyncIterator([block_start, text_event, block_stop]))
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_mimo = MagicMock()
    mock_mimo.model = "mimo-v2.5"
    mock_mimo.client.messages.stream = MagicMock(return_value=mock_stream_ctx)

    with patch("app.utils.chat_orchestrator._build_local_tool_definitions", return_value=[]):
        events = []
        async for event in run_chat([{"role": "user", "content": "Hi"}], mock_mimo, MagicMock(), MagicMock()):
            events.append(event)

    assert any(e["type"] == "text" and e["content"] == "Hello!" for e in events)
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_run_chat_error_yields_error():
    """Exception during streaming yields error event."""
    from app.utils.chat_orchestrator import run_chat

    mock_mimo = MagicMock()
    mock_mimo.model = "mimo-v2.5"
    mock_mimo.client.messages.stream = MagicMock(side_effect=Exception("API down"))

    with patch("app.utils.chat_orchestrator._build_local_tool_definitions", return_value=[]):
        events = []
        async for event in run_chat([{"role": "user", "content": "Hi"}], mock_mimo, MagicMock(), MagicMock()):
            events.append(event)

    assert events[0]["type"] == "error"
    assert "API down" in events[0]["detail"]
