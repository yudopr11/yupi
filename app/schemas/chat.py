from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ImageBlock(BaseModel):
    media_type: str
    data: str  # base64-encoded


class ChatRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    message: str
    images: Optional[list[ImageBlock]] = None


class ToolCallResponse(BaseModel):
    id: UUID
    tool_name: str
    arguments: Optional[dict] = None
    result: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    tool_calls: list[ToolCallResponse] = []
    images: Optional[list[ImageBlock]] = None

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_preview: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = []


class ConversationUpdate(BaseModel):
    title: str


class McpEndpoint(BaseModel):
    name: str
    url: str


class SettingsResponse(BaseModel):
    mimo_api_key: Optional[str] = None
    mimo_base_url: Optional[str] = None
    mimo_model: Optional[str] = None
    mcp_endpoints: Optional[list[McpEndpoint]] = None


class McpAction(BaseModel):
    remove_indices: Optional[list[int]] = None
    add: Optional[list[McpEndpoint]] = None


class SettingsUpdate(BaseModel):
    mimo_api_key: Optional[str] = None
    mimo_base_url: Optional[str] = None
    mimo_model: Optional[str] = None
    mcp_endpoints: Optional[list[str]] = None
    mcp_action: Optional[McpAction] = None
