"""add chat tables

Revision ID: a1b2c3d4e5f6
Revises: dbcead8c70d2
Create Date: 2026-05-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'dbcead8c70d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(), nullable=False, server_default='New Chat'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('auth_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_chat_conversations_user_id', 'chat_conversations', ['user_id'])

    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])

    op.create_table(
        'chat_tool_calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chat_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('arguments', postgresql.JSON(), nullable=True),
        sa.Column('result', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_chat_tool_calls_message_id', 'chat_tool_calls', ['message_id'])

    op.create_table(
        'chat_user_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('auth_users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('mimo_api_key', sa.Text(), nullable=True),
        sa.Column('mimo_base_url', sa.String(), nullable=True),
        sa.Column('mimo_model', sa.String(), nullable=True),
        sa.Column('mcp_endpoint', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_chat_user_settings_user_id', 'chat_user_settings', ['user_id'])


def downgrade() -> None:
    op.drop_table('chat_user_settings')
    op.drop_table('chat_tool_calls')
    op.drop_table('chat_messages')
    op.drop_table('chat_conversations')
