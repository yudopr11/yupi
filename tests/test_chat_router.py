"""Tests for app/routers/chat.py endpoints."""
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch
from app.utils.uuid import uuid7

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# _get_user_mimo_config
# ---------------------------------------------------------------------------

def test_get_user_mimo_config_from_env():
    """Falls back to env defaults when no user settings exist."""
    from app.routers.chat import _get_user_mimo_config

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_user = MagicMock()
    mock_user.id = uuid7()

    with patch("app.routers.chat.app_settings") as mock_settings:
        mock_settings.MIMO_API_KEY = "env-key"
        mock_settings.MIMO_BASE_URL = "https://env.url"
        mock_settings.MIMO_MODEL = "env-model"

        api_key, base_url, model, mcp_endpoint = _get_user_mimo_config(mock_db, mock_user)

    assert api_key == "env-key"
    assert base_url == "https://env.url"
    assert model == "env-model"


def test_get_user_mimo_config_from_user_settings():
    """User settings override env defaults."""
    from app.routers.chat import _get_user_mimo_config

    mock_us = MagicMock()
    mock_us.mimo_api_key = "user-key"
    mock_us.mimo_base_url = "https://user.url"
    mock_us.mimo_model = "user-model"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_us
    mock_user = MagicMock()
    mock_user.id = uuid7()

    api_key, base_url, model, mcp_endpoint = _get_user_mimo_config(mock_db, mock_user)

    assert api_key == "user-key"
    assert base_url == "https://user.url"
    assert model == "user-model"


def test_get_user_mimo_config_no_key_raises():
    """Raises 400 when no API key is configured anywhere."""
    from app.routers.chat import _get_user_mimo_config

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_user = MagicMock()

    with patch("app.routers.chat.app_settings") as mock_settings:
        mock_settings.MIMO_API_KEY = ""
        mock_settings.MIMO_BASE_URL = "https://x.com"
        mock_settings.MIMO_MODEL = "m"

        with pytest.raises(HTTPException) as exc_info:
            _get_user_mimo_config(mock_db, mock_user)

    assert exc_info.value.status_code == 400
    assert "API key" in exc_info.value.detail


def test_get_user_mimo_config_partial_user_settings():
    """User can override just model, rest falls back to env."""
    from app.routers.chat import _get_user_mimo_config

    mock_us = MagicMock()
    mock_us.mimo_api_key = None
    mock_us.mimo_base_url = None
    mock_us.mimo_model = "custom-model"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_us
    mock_user = MagicMock()

    with patch("app.routers.chat.app_settings") as mock_settings:
        mock_settings.MIMO_API_KEY = "env-key"
        mock_settings.MIMO_BASE_URL = "https://env.url"
        mock_settings.MIMO_MODEL = "env-model"

        api_key, base_url, model, mcp_endpoint = _get_user_mimo_config(mock_db, mock_user)

    assert api_key == "env-key"
    assert base_url == "https://env.url"
    assert model == "custom-model"


# ---------------------------------------------------------------------------
# _load_conversation_messages
# ---------------------------------------------------------------------------

def test_load_conversation_messages_user_msg():
    """User messages load as simple role+content dict."""
    from app.routers.chat import _load_conversation_messages

    msg = MagicMock()
    msg.role = "user"
    msg.content = "Hello"
    msg.content_blocks = None
    msg.tool_calls = []
    msg.created_at = datetime.now(UTC)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]

    result = _load_conversation_messages(mock_db, uuid7())

    assert len(result) == 1
    assert result[0] == {"role": "user", "content": "Hello"}


def test_load_conversation_messages_assistant_with_tools():
    """Assistant messages with tool_calls produce content blocks."""
    from app.routers.chat import _load_conversation_messages

    tc = MagicMock()
    tc.id = uuid7()
    tc.tool_name = "get_accounts"
    tc.arguments = {"limit": 5}

    msg = MagicMock()
    msg.role = "assistant"
    msg.content = "Here are your accounts"
    msg.tool_calls = [tc]
    msg.created_at = datetime.now(UTC)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]

    result = _load_conversation_messages(mock_db, uuid7())

    # Should be 2 messages: assistant with tool_use + user with tool_result
    assert len(result) == 2
    # First: assistant message with text + tool_use content blocks
    content = result[0]["content"]
    assert result[0]["role"] == "assistant"
    assert content[0] == {"type": "text", "text": "Here are your accounts"}
    assert content[1]["type"] == "tool_use"
    assert content[1]["name"] == "get_accounts"
    # Second: user message with tool_result content block
    assert result[1]["role"] == "user"
    tool_result = result[1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert str(tool_result["tool_use_id"]) == str(tc.id)


def test_load_conversation_messages_skips_tool_role():
    """Tool role messages are skipped (loaded from tool_calls)."""
    from app.routers.chat import _load_conversation_messages

    msg = MagicMock()
    msg.role = "tool"
    msg.content = "{}"
    msg.tool_calls = []
    msg.created_at = datetime.now(UTC)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]

    result = _load_conversation_messages(mock_db, uuid7())
    assert len(result) == 0
