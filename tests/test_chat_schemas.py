"""Tests for app/schemas/chat.py Pydantic schemas."""
from datetime import datetime, UTC
from app.utils.uuid import uuid7

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# ChatRequest
# ---------------------------------------------------------------------------

def test_chat_request_valid_with_conversation():
    from app.schemas.chat import ChatRequest
    schema = ChatRequest(conversation_id=uuid7(), message="Hello")
    assert schema.message == "Hello"
    assert schema.conversation_id is not None


def test_chat_request_valid_without_conversation():
    from app.schemas.chat import ChatRequest
    schema = ChatRequest(message="Hello")
    assert schema.conversation_id is None


def test_chat_request_missing_message_raises():
    from app.schemas.chat import ChatRequest
    with pytest.raises(ValidationError):
        ChatRequest()


def test_chat_request_empty_message_rejected():
    from app.schemas.chat import ChatRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ChatRequest(message="")


# ---------------------------------------------------------------------------
# ToolCallResponse
# ---------------------------------------------------------------------------

def test_tool_call_response_valid():
    from app.schemas.chat import ToolCallResponse
    schema = ToolCallResponse(
        id=uuid7(),
        tool_name="get_accounts",
        arguments={"limit": 10},
        result={"accounts": []},
        status="completed",
        created_at=datetime.now(UTC),
    )
    assert schema.tool_name == "get_accounts"
    assert schema.status == "completed"
    assert schema.error_message is None
    assert schema.completed_at is None


def test_tool_call_response_error():
    from app.schemas.chat import ToolCallResponse
    schema = ToolCallResponse(
        id=uuid7(),
        tool_name="bad_tool",
        status="error",
        error_message="Tool not found",
        created_at=datetime.now(UTC),
    )
    assert schema.error_message == "Tool not found"


def test_tool_call_response_missing_required_raises():
    from app.schemas.chat import ToolCallResponse
    with pytest.raises(ValidationError):
        ToolCallResponse(tool_name="x", status="ok")


# ---------------------------------------------------------------------------
# MessageResponse
# ---------------------------------------------------------------------------

def test_message_response_valid():
    from app.schemas.chat import MessageResponse
    schema = MessageResponse(
        id=uuid7(),
        role="assistant",
        content="Hello!",
        created_at=datetime.now(UTC),
    )
    assert schema.role == "assistant"
    assert schema.tool_calls == []


def test_message_response_with_tool_calls():
    from app.schemas.chat import MessageResponse, ToolCallResponse
    tc = ToolCallResponse(
        id=uuid7(), tool_name="x", status="completed",
        created_at=datetime.now(UTC),
    )
    schema = MessageResponse(
        id=uuid7(), role="assistant", content="",
        created_at=datetime.now(UTC), tool_calls=[tc],
    )
    assert len(schema.tool_calls) == 1


# ---------------------------------------------------------------------------
# ConversationResponse
# ---------------------------------------------------------------------------

def test_conversation_response_valid():
    from app.schemas.chat import ConversationResponse
    schema = ConversationResponse(
        id=uuid7(),
        title="My Chat",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert schema.title == "My Chat"
    assert schema.last_message_preview is None


def test_conversation_response_with_preview():
    from app.schemas.chat import ConversationResponse
    schema = ConversationResponse(
        id=uuid7(),
        title="Chat",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_message_preview="Hello world",
    )
    assert schema.last_message_preview == "Hello world"


# ---------------------------------------------------------------------------
# ConversationDetailResponse
# ---------------------------------------------------------------------------

def test_conversation_detail_response_inherits():
    from app.schemas.chat import ConversationDetailResponse
    schema = ConversationDetailResponse(
        id=uuid7(),
        title="Chat",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert schema.messages == []


def test_conversation_detail_response_with_messages():
    from app.schemas.chat import ConversationDetailResponse, MessageResponse
    msg = MessageResponse(
        id=uuid7(), role="user", content="Hi",
        created_at=datetime.now(UTC),
    )
    schema = ConversationDetailResponse(
        id=uuid7(), title="Chat",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        messages=[msg],
    )
    assert len(schema.messages) == 1


# ---------------------------------------------------------------------------
# ConversationUpdate
# ---------------------------------------------------------------------------

def test_conversation_update_valid():
    from app.schemas.chat import ConversationUpdate
    schema = ConversationUpdate(title="New Title")
    assert schema.title == "New Title"


def test_conversation_update_missing_title_raises():
    from app.schemas.chat import ConversationUpdate
    with pytest.raises(ValidationError):
        ConversationUpdate()


# ---------------------------------------------------------------------------
# SettingsResponse / SettingsUpdate
# ---------------------------------------------------------------------------

def test_settings_response_all_none():
    from app.schemas.chat import SettingsResponse
    schema = SettingsResponse()
    assert schema.mimo_api_key is None
    assert schema.mimo_base_url is None


def test_settings_response_with_values():
    from app.schemas.chat import SettingsResponse
    schema = SettingsResponse(
        mimo_api_key="sk-1234...",
        mimo_base_url="https://example.com",
        mimo_model="mimo-v2.5",
        mcp_endpoints=[],
    )
    assert schema.mimo_model == "mimo-v2.5"


def test_settings_update_partial():
    from app.schemas.chat import SettingsUpdate
    schema = SettingsUpdate(mimo_model="new-model")
    assert schema.mimo_model == "new-model"
    assert schema.mimo_api_key is None


def test_settings_update_empty():
    from app.schemas.chat import SettingsUpdate
    schema = SettingsUpdate()
    assert schema.mimo_api_key is None
    assert schema.mimo_base_url is None
    assert schema.mimo_model is None
    assert schema.mcp_endpoints is None
