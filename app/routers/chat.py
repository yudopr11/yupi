import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.utils.database import get_db
from app.utils.auth import get_current_user
from app.core.config import settings as app_settings
from app.models.auth import User
from app.models.chat import Conversation, ChatMessage, ToolCall, UserSettings
from app.schemas.chat import (
    ChatRequest,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationUpdate,
    MessageResponse,
    ToolCallResponse,
    ImageBlock,
    SettingsResponse,
    SettingsUpdate,
    McpEndpoint,
)
from app.utils.mimo_client import MiMoClient
from app.utils.mcp_client import mcp_pool
from app.utils.chat_orchestrator import run_chat
from app.utils.crypto import encrypt_value, decrypt_value, mask_value, encrypt_endpoint, decrypt_endpoint

router = APIRouter(prefix="/chat", tags=["Chat"])


def _decrypt_safe(value: str | None) -> str | None:
    """Decrypt a value, falling back to plaintext if decryption fails (old data)."""
    if not value:
        return value
    try:
        return decrypt_value(value)
    except Exception:
        return value


def _get_user_mimo_config(db: Session, user: User) -> tuple[str, str, str, list[str]]:
    """Get MiMo config: user override > env default. Returns (api_key, base_url, model, mcp_endpoints)."""
    us = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    api_key = (_decrypt_safe(us.mimo_api_key) if us and us.mimo_api_key else None) or app_settings.MIMO_API_KEY
    base_url = (us.mimo_base_url if us and us.mimo_base_url else None) or app_settings.MIMO_BASE_URL
    model = (us.mimo_model if us and us.mimo_model else None) or app_settings.MIMO_MODEL
    mcp_endpoints = [decrypt_endpoint(ep)["url"] for ep in us.mcp_endpoints] if us and us.mcp_endpoints else []
    if not api_key:
        raise HTTPException(status_code=400, detail="MiMo API key not configured. Set it in Settings.")
    return api_key, base_url, model, mcp_endpoints


def _load_conversation_messages(db: Session, conversation_id: UUID) -> list[dict]:
    """Load conversation history in Anthropic messages format."""
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    result = []
    for msg in messages:
        if msg.role == "tool":
            # Tool results are loaded from the tool_calls of the previous assistant message
            continue
        if msg.role == "assistant" and msg.tool_calls:
            content = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": str(tc.id),
                    "name": tc.tool_name,
                    "input": tc.arguments or {},
                })
            result.append({"role": "assistant", "content": content})
        elif msg.role == "user":
            if msg.content_blocks:
                result.append({"role": "user", "content": msg.content_blocks})
            else:
                result.append({"role": "user", "content": msg.content})
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


@router.post("")
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    api_key, base_url, model, mcp_endpoints = _get_user_mimo_config(db, current_user)

    # Create or load conversation
    if body.conversation_id:
        conv = db.query(Conversation).filter(
            Conversation.id == body.conversation_id,
            Conversation.user_id == current_user.id,
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(user_id=current_user.id, title="New Chat")
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Save user message
    content_blocks = None
    if body.images:
        content_blocks = [{"type": "text", "text": body.message}]
        for img in body.images:
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.media_type,
                    "data": img.data,
                },
            })

    user_msg = ChatMessage(
        conversation_id=conv.id,
        role="user",
        content=body.message,
        content_blocks=content_blocks,
    )
    db.add(user_msg)
    db.commit()

    # Update title from first message
    if conv.title == "New Chat":
        conv.title = body.message[:80] + ("..." if len(body.message) > 80 else "")
        db.commit()

    # Load full conversation history
    history = _load_conversation_messages(db, conv.id)

    # Create MiMo client
    mimo = MiMoClient(api_key=api_key, base_url=base_url, model=model)

    conversation_id = str(conv.id)

    async def _stream_events(tool_sessions, remote_tools=None):
        assistant_content = ""
        tool_calls_data = []

        async for event in run_chat(history, mimo, current_user, db, tool_sessions, remote_tools):
            if event["type"] == "text":
                assistant_content += event["content"]
                yield f"event: delta\ndata: {json.dumps({'content': event['content']})}\n\n"
            elif event["type"] == "tool_start":
                tool_calls_data.append({"id": event["id"], "name": event["name"], "arguments": event["arguments"], "result": None})
                yield f"event: tool_start\ndata: {json.dumps({'id': event['id'], 'name': event['name'], 'arguments': event['arguments']})}\n\n"
            elif event["type"] == "tool_end":
                for tc in tool_calls_data:
                    if tc["id"] == event["id"]:
                        tc["result"] = event["result"]
                yield f"event: tool_end\ndata: {json.dumps({'id': event['id'], 'name': event['name'], 'result': event['result']})}\n\n"
            elif event["type"] == "error":
                yield f"event: error\ndata: {json.dumps({'detail': event['detail']})}\n\n"
            elif event["type"] == "done":
                # Save assistant message + tool calls to DB
                assistant_msg = ChatMessage(
                    conversation_id=UUID(conversation_id),
                    role="assistant",
                    content=assistant_content,
                )
                db.add(assistant_msg)
                db.flush()
                for tc in tool_calls_data:
                    tool_call = ToolCall(
                        message_id=assistant_msg.id,
                        tool_name=tc["name"],
                        arguments=tc["arguments"],
                        result=tc["result"],
                        status="completed" if tc["result"] else "error",
                    )
                    db.add(tool_call)
                db.commit()
                yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id, 'message_id': str(assistant_msg.id)})}\n\n"

    async def event_stream():
        try:
            if mcp_endpoints:
                result = await mcp_pool.get_sessions(str(current_user.id), mcp_endpoints)
                if result:
                    tool_sessions, remote_tools = result
                    async for chunk in _stream_events(tool_sessions, remote_tools):
                        yield chunk
                else:
                    async for chunk in _stream_events(None):
                        yield chunk
            else:
                async for chunk in _stream_events(None):
                    yield chunk
        except Exception as e:
            db.rollback()
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    result = []
    for conv in convs:
        last_msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        preview = last_msg.content[:100] if last_msg else None
        result.append(ConversationResponse(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            last_message_preview=preview,
        ))
    return result


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    msg_responses = []
    for msg in messages:
        tcs = [
            ToolCallResponse(
                id=tc.id,
                tool_name=tc.tool_name,
                arguments=tc.arguments,
                result=tc.result,
                status=tc.status,
                error_message=tc.error_message,
                created_at=tc.created_at,
                completed_at=tc.completed_at,
            )
            for tc in msg.tool_calls
        ]
        # Extract images from content_blocks if present
        images = None
        if msg.content_blocks:
            images = [
                ImageBlock(
                    media_type=block["source"]["media_type"],
                    data=block["source"]["data"],
                )
                for block in msg.content_blocks
                if block.get("type") == "image" and block.get("source")
            ] or None

        msg_responses.append(MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            tool_calls=tcs,
            images=images,
        ))

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=msg_responses,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = body.title
    db.commit()
    db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"detail": "Deleted"}


# --- Settings ---


def _get_or_create_settings(db: Session, user_id) -> UserSettings:
    us = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not us:
        us = UserSettings(user_id=user_id)
        db.add(us)
        db.commit()
        db.refresh(us)
    return us


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    us = _get_or_create_settings(db, current_user.id)
    api_key = _decrypt_safe(us.mimo_api_key) or app_settings.MIMO_API_KEY
    endpoints = []
    for ep in (us.mcp_endpoints or []):
        data = decrypt_endpoint(ep)
        endpoints.append(McpEndpoint(name=data["name"], url=mask_value(data["url"])))
    return SettingsResponse(
        mimo_api_key=mask_value(api_key),
        mimo_base_url=us.mimo_base_url or app_settings.MIMO_BASE_URL,
        mimo_model=us.mimo_model or app_settings.MIMO_MODEL,
        mcp_endpoints=endpoints,
    )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    us = _get_or_create_settings(db, current_user.id)
    if body.mimo_api_key is not None:
        us.mimo_api_key = encrypt_value(body.mimo_api_key)
    if body.mimo_base_url is not None:
        us.mimo_base_url = body.mimo_base_url
    if body.mimo_model is not None:
        us.mimo_model = body.mimo_model

    # Handle MCP endpoint changes via mcp_action
    if body.mcp_action:
        existing = list(us.mcp_endpoints or [])
        action = body.mcp_action

        # Remove by index (descending to preserve indices)
        if action.remove_indices:
            for idx in sorted(action.remove_indices, reverse=True):
                if 0 <= idx < len(existing):
                    existing.pop(idx)

        # Add new endpoints (encrypt each)
        if action.add:
            for ep in action.add:
                existing.append(encrypt_endpoint(ep.name, ep.url))

        us.mcp_endpoints = existing
    elif body.mcp_endpoints is not None:
        # Direct replacement (backward compat)
        us.mcp_endpoints = [encrypt_value(ep) for ep in body.mcp_endpoints]

    db.commit()
    db.refresh(us)

    # Invalidate MCP connection pool so new endpoints take effect
    await mcp_pool.invalidate(str(current_user.id))

    api_key = _decrypt_safe(us.mimo_api_key) or app_settings.MIMO_API_KEY
    endpoints = []
    for ep in (us.mcp_endpoints or []):
        data = decrypt_endpoint(ep)
        endpoints.append(McpEndpoint(name=data["name"], url=mask_value(data["url"])))
    return SettingsResponse(
        mimo_api_key=mask_value(api_key),
        mimo_base_url=us.mimo_base_url or app_settings.MIMO_BASE_URL,
        mimo_model=us.mimo_model or app_settings.MIMO_MODEL,
        mcp_endpoints=endpoints,
    )
