import json
import logging
from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

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
from app.utils.mcp_client import mcp_pool, validate_mcp_endpoint
from app.utils.chat_orchestrator import run_chat
from app.utils.crypto import encrypt_value, decrypt_value, mask_value, encrypt_endpoint, decrypt_endpoint

router = APIRouter(prefix="/chat", tags=["Chat"])

logger = logging.getLogger(__name__)


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
    mcp_endpoints = []
    if us and us.mcp_endpoints:
        for ep in us.mcp_endpoints:
            data = decrypt_endpoint(ep)
            if data is None:
                continue
            mcp_endpoints.append(data["url"])
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
            tool_results = []
            for tc in msg.tool_calls:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": str(tc.id),
                    "content": tc.result if tc.result else "",
                })
            if tool_results:
                result.append({"role": "user", "content": tool_results})
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
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Conflict")
        except Exception:
            db.rollback()
            raise
        db.refresh(conv)

    # Save user message
    content_blocks = None
    if body.images:
        content_blocks = []
        if body.message:
            content_blocks.append({"type": "text", "text": body.message})
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflict")
    except Exception:
        db.rollback()
        raise

    # Update title from first message
    if conv.title == "New Chat":
        title_src = body.message[:80] if body.message else "Image"
        conv.title = title_src + ("..." if len(title_src) >= 80 else "")
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Conflict")
        except Exception:
            db.rollback()
            raise

    # Load full conversation history
    history = _load_conversation_messages(db, conv.id)

    # Create MiMo client
    mimo = MiMoClient(api_key=api_key, base_url=base_url, model=model)

    conversation_id = str(conv.id)

    async def _stream_events(conn_map=None, remote_tools=None):
        assistant_content = ""
        tool_calls_data = []

        def _save_round(content: str, tool_calls: list[dict]) -> str | None:
            """Save one assistant message + its tool calls. Returns message ID or None on error."""
            assistant_msg = ChatMessage(
                conversation_id=UUID(conversation_id),
                role="assistant",
                content=content,
            )
            db.add(assistant_msg)
            db.flush()
            now = datetime.now(UTC)
            for tc in tool_calls:
                tool_call = ToolCall(
                    message_id=assistant_msg.id,
                    tool_name=tc["name"],
                    arguments=tc["arguments"],
                    result=tc["result"],
                    status="completed" if tc["result"] is not None else "error",
                    completed_at=now,
                )
                db.add(tool_call)
            try:
                db.flush()
            except Exception:
                db.rollback()
                logging.exception("Failed to save tool round")
                return None
            return str(assistant_msg.id)

        async for event in run_chat(history, mimo, current_user, db, conn_map, remote_tools):
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
            elif event["type"] == "persist":
                # Save this tool round as a separate assistant message
                msg_id = _save_round(assistant_content, tool_calls_data)
                if msg_id is None:
                    yield f"event: error\ndata: {json.dumps({'detail': 'Failed to save conversation'})}\n\n"
                    return
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    logging.exception("Failed to commit tool round")
                    yield f"event: error\ndata: {json.dumps({'detail': 'Failed to save conversation'})}\n\n"
                    return
                yield f"event: tool_round_saved\ndata: {json.dumps({'message_id': msg_id})}\n\n"
                # Reset accumulators for next round
                assistant_content = ""
                tool_calls_data = []
            elif event["type"] == "done":
                # Final round — save remaining content (may be empty if last round was tools)
                if assistant_content or tool_calls_data:
                    msg_id = _save_round(assistant_content, tool_calls_data)
                    if msg_id is None:
                        yield f"event: error\ndata: {json.dumps({'detail': 'Failed to save conversation'})}\n\n"
                        return
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    logging.exception("Failed to commit conversation")
                    yield f"event: error\ndata: {json.dumps({'detail': 'Failed to save conversation'})}\n\n"
                    return
                yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"

    async def event_stream():
        try:
            conn_map = None
            remote_tools = None
            if mcp_endpoints:
                try:
                    result = await mcp_pool.get_sessions(str(current_user.id), mcp_endpoints)
                    if result:
                        conn_map, remote_tools = result
                    else:
                        logger.warning("MCP pool returned no sessions, falling back to local tools")
                except Exception:
                    logger.exception("MCP connection failed, falling back to local tools")

            async for chunk in _stream_events(conn_map, remote_tools):
                yield chunk
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                logger.exception("Error during rollback")
            logging.exception("Chat stream error")
            yield f"event: error\ndata: {json.dumps({'detail': 'An internal error occurred'})}\n\n"
            yield f"event: done\ndata: {json.dumps({'conversation_id': None, 'message_id': None})}\n\n"

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
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not convs:
        return []

    # Bulk fetch last message per conversation (no N+1)
    conv_ids = [c.id for c in convs]
    from sqlalchemy import func as sa_func
    subq = (
        db.query(
            ChatMessage.conversation_id,
            ChatMessage.content,
            sa_func.row_number().over(
                partition_by=ChatMessage.conversation_id,
                order_by=ChatMessage.created_at.desc(),
            ).label("rn"),
        )
        .filter(ChatMessage.conversation_id.in_(conv_ids))
        .subquery()
    )
    last_msgs = {
        row.conversation_id: row.content[:100]
        for row in db.query(subq).filter(subq.c.rn == 1).all()
    }

    return [
        ConversationResponse(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            last_message_preview=last_msgs.get(conv.id),
        )
        for conv in convs
    ]


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
        .options(joinedload(ChatMessage.tool_calls))
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflict")
    except Exception:
        db.rollback()
        raise
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
    info = {"id": str(conv.id), "title": conv.title}
    db.delete(conv)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflict")
    except Exception:
        db.rollback()
        raise
    return {"message": "Conversation deleted", "deleted_item": info}


# --- Settings ---


def _get_or_create_settings(db: Session, user_id) -> UserSettings:
    us = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not us:
        us = UserSettings(user_id=user_id)
        db.add(us)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Conflict")
        except Exception:
            db.rollback()
            raise
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
        if data is None:
            continue
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
        if body.mimo_base_url and not body.mimo_base_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="mimo_base_url must start with http:// or https://")
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

        # Add new endpoints (encrypt each), skip duplicates by URL
        if action.add:
            existing_urls = set()
            for enc_ep in existing:
                data = decrypt_endpoint(enc_ep)
                if data:
                    existing_urls.add(data["url"])
            for ep in action.add:
                try:
                    validate_mcp_endpoint(ep.url)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid MCP endpoint: {exc}")
                if ep.url not in existing_urls:
                    existing.append(encrypt_endpoint(ep.name, ep.url))
                    existing_urls.add(ep.url)

        us.mcp_endpoints = existing
    elif body.mcp_endpoints is not None:
        # Direct replacement (backward compat) — wrap in dict structure for decrypt_endpoint
        for ep in body.mcp_endpoints:
            try:
                validate_mcp_endpoint(ep)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid MCP endpoint: {exc}")
        us.mcp_endpoints = [encrypt_endpoint("", ep) for ep in body.mcp_endpoints]

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflict")
    except Exception:
        db.rollback()
        raise
    db.refresh(us)

    # Invalidate MCP connection pool so new endpoints take effect
    await mcp_pool.invalidate(str(current_user.id))

    api_key = _decrypt_safe(us.mimo_api_key) or app_settings.MIMO_API_KEY
    endpoints = []
    for ep in (us.mcp_endpoints or []):
        data = decrypt_endpoint(ep)
        if data is None:
            continue
        endpoints.append(McpEndpoint(name=data["name"], url=mask_value(data["url"])))
    return SettingsResponse(
        mimo_api_key=mask_value(api_key),
        mimo_base_url=us.mimo_base_url or app_settings.MIMO_BASE_URL,
        mimo_model=us.mimo_model or app_settings.MIMO_MODEL,
        mcp_endpoints=endpoints,
    )
