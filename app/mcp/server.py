"""Embedded MCP server for yupi. Mounts at /mcp/{base64(user:pass)}."""
import base64
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from app.models.auth import User
from app.mcp.context import _current_db_var, _current_user_var
from app.mcp.tools import (
    analyze_bill_impl,
    cleanup_guest_data_impl,
    cleanup_orphans_impl,
    create_account_impl,
    create_category_impl,
    create_post_impl,
    create_transaction_impl,
    create_transaction_from_receipt_impl,
    delete_account_impl,
    delete_category_impl,
    delete_file_impl,
    delete_post_impl,
    delete_transaction_impl,
    delete_user_impl,
    get_account_balance_impl,
    get_account_summary_impl,
    get_category_distribution_impl,
    get_current_user_impl,
    get_financial_summary_impl,
    get_post_impl,
    get_trends_impl,
    list_accounts_impl,
    list_all_users_impl,
    list_categories_impl,
    list_files_impl,
    list_posts_impl,
    list_transactions_impl,
    register_user_impl,
    update_account_impl,
    update_category_impl,
    update_post_impl,
    update_transaction_impl,
)
from app.core.config import settings
from app.utils.auth import verify_password
from app.utils.database import SessionLocal

# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "yupi",
    # DNS rebinding protection disabled for local dev; enable in production via env flag
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=settings.MCP_DNS_REBINDING_PROTECTION),
)

if not settings.MCP_DNS_REBINDING_PROTECTION:
    logger.warning("MCP DNS rebinding protection is DISABLED. Set MCP_DNS_REBINDING_PROTECTION=True in production.")


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_current_user() -> dict:
    """Get the currently authenticated user's info."""
    return await get_current_user_impl()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_all_users() -> list:
    """List all registered users. Requires superuser."""
    return await list_all_users_impl()


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def register_user(username: str, email: str, password: str, is_superuser: bool = False) -> dict:
    """Register a new user. Requires superuser."""
    return await register_user_impl(username, email, password, is_superuser)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def delete_user(user_id: str) -> dict:
    """Delete a user by UUID. Requires superuser."""
    return await delete_user_impl(user_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_posts(
    skip: int = 0,
    limit: int = 10,
    cursor: Optional[str] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    published_status: str = "published",
    use_rag: bool = False,
) -> dict:
    """List blog posts with optional filters. published_status: published|unpublished|all. cursor = ISO datetime from next_cursor."""
    return await list_posts_impl(skip, limit, cursor, search, tag, published_status, use_rag)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_post(slug: str) -> dict:
    """Get a single blog post by URL slug."""
    return await get_post_impl(slug)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def create_post(
    title: str,
    content: str,
    published: bool = False,
    tags: Optional[list[str]] = None,
    excerpt: Optional[str] = None,
) -> dict:
    """Create a blog post. Tags and excerpt auto-generated if omitted."""
    return await create_post_impl(title, content, published, tags, excerpt)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def update_post(
    post_id: str,
    title: str,
    content: str,
    published: bool = False,
    tags: Optional[list[str]] = None,
    excerpt: Optional[str] = None,
) -> dict:
    """Update a blog post by UUID."""
    return await update_post_impl(post_id, title, content, published, tags, excerpt)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def delete_post(post_id: str) -> dict:
    """Delete a blog post by UUID. Superuser only."""
    return await delete_post_impl(post_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_accounts(account_type: Optional[str] = None, year: Optional[int] = None) -> list:
    """List financial accounts with balances. account_type: bank_account|credit_card|other."""
    return await list_accounts_impl(account_type, year)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_account_balance(account_id: str, year: Optional[int] = None) -> dict:
    """Get detailed balance for a single account by UUID."""
    return await get_account_balance_impl(account_id, year)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def create_account(
    name: str,
    type: str,
    description: Optional[str] = None,
    limit: Optional[float] = None,
    account_number: Optional[str] = None,
) -> dict:
    """Create a financial account. type: bank_account|credit_card|other. account_number required for bank_account/credit_card."""
    return await create_account_impl(name, type, description, limit, account_number)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def update_account(
    account_id: str,
    name: str,
    type: str,
    description: Optional[str] = None,
    limit: Optional[float] = None,
    account_number: Optional[str] = None,
) -> dict:
    """Update a financial account by UUID. account_number required for bank_account/credit_card."""
    return await update_account_impl(account_id, name, type, description, limit, account_number)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def delete_account(account_id: str) -> dict:
    """Delete a financial account by UUID."""
    return await delete_account_impl(account_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_categories(category_type: Optional[str] = None) -> list:
    """List transaction categories. category_type: income|expense."""
    return await list_categories_impl(category_type)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def create_category(name: str, type: str) -> dict:
    """Create a transaction category. type: income|expense."""
    return await create_category_impl(name, type)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def update_category(category_id: str, name: str, type: str) -> dict:
    """Update a transaction category by UUID."""
    return await update_category_impl(category_id, name, type)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def delete_category(category_id: str) -> dict:
    """Delete a transaction category by UUID."""
    return await delete_category_impl(category_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_transactions(
    account_name: Optional[str] = None,
    category_name: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date_filter_type: Optional[str] = None,
    timezone: str = "UTC",
    order_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 10,
    skip: int = 0,
    cursor: Optional[str] = None,
) -> dict:
    """List transactions with filters. Supports cursor pagination (cursor = ISO datetime from next_cursor). transaction_type: income|expense|transfer."""
    return await list_transactions_impl(
        account_name, category_name, transaction_type,
        start_date, end_date, date_filter_type,
        timezone, order_by, sort_order, limit, skip, cursor,
    )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def create_transaction(
    transaction_date: str,
    description: str,
    amount: float,
    transaction_type: str,
    account_id: str,
    category_id: Optional[str] = None,
    destination_account_id: Optional[str] = None,
    transfer_fee: Optional[float] = None,
) -> dict:
    """Create a transaction. transaction_type: income|expense|transfer. transaction_date must be ISO 8601 with time (e.g. 2026-05-28T14:30:00+00:00)."""
    return await create_transaction_impl(
        transaction_date, description, amount, transaction_type,
        account_id, category_id, destination_account_id, transfer_fee,
    )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def create_transaction_from_receipt(
    base64_image: str,
    media_type: str,
    transaction_date: str,
    description: str,
    amount: float,
    transaction_type: str,
    account_id: str,
    category_id: Optional[str] = None,
    destination_account_id: Optional[str] = None,
    transfer_fee: Optional[float] = None,
) -> dict:
    """Create a transaction with a receipt image. Use when the user sends a receipt/photo and wants to record it as a transaction. base64_image: raw base64 (no data: prefix). media_type: e.g. image/jpeg. transaction_type: income|expense|transfer. transaction_date: ISO 8601 with time."""
    return await create_transaction_from_receipt_impl(
        base64_image, media_type, transaction_date, description, amount,
        transaction_type, account_id, category_id, destination_account_id, transfer_fee,
    )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def update_transaction(
    transaction_id: str,
    transaction_date: str,
    description: str,
    amount: float,
    transaction_type: str,
    account_id: str,
    category_id: Optional[str] = None,
    destination_account_id: Optional[str] = None,
    transfer_fee: Optional[float] = None,
) -> dict:
    """Update a transaction by UUID. transaction_date must be ISO 8601 with time (e.g. 2026-05-28T14:30:00+00:00)."""
    return await update_transaction_impl(
        transaction_id, transaction_date, description, amount,
        transaction_type, account_id, category_id, destination_account_id, transfer_fee,
    )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def delete_transaction(transaction_id: str) -> dict:
    """Delete a transaction by UUID."""
    return await delete_transaction_impl(transaction_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_financial_summary(
    period: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timezone: str = "UTC",
) -> dict:
    """Get financial summary. period: day|week|month|year|all."""
    return await get_financial_summary_impl(period, start_date, end_date, timezone)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_category_distribution(
    transaction_type: str = "expense",
    period: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timezone: str = "UTC",
) -> dict:
    """Get transaction distribution by category. transaction_type: income|expense."""
    return await get_category_distribution_impl(transaction_type, period, start_date, end_date, timezone)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_trends(
    period: str = "month",
    group_by: str = "day",
    transaction_types: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timezone: str = "UTC",
) -> dict:
    """Get transaction trends. group_by: day|week|month."""
    return await get_trends_impl(period, group_by, transaction_types, start_date, end_date, timezone)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_account_summary() -> dict:
    """Get account summary: total balance, credit utilization, per-account details."""
    return await get_account_summary_impl()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def analyze_bill(
    image_path: str,
    description: str,
    image_description: Optional[str] = None,
) -> dict:
    """Analyze a bill image and split costs. image_path: absolute path (JPEG/PNG/WebP, max 5MB)."""
    return await analyze_bill_impl(image_path, description, image_description)


# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_files(limit: int = 50) -> list:
    """List current user's uploaded files (receipts, etc)."""
    return await list_files_impl(limit)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def delete_file(file_id: str) -> dict:
    """Mark a file as orphan (soft delete). Owner or superuser only."""
    return await delete_file_impl(file_id)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def cleanup_orphaned_files() -> dict:
    """Delete all orphaned files from storage and DB. Superuser only."""
    return await cleanup_orphans_impl()


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def cleanup_guest_data(days: int = 30) -> dict:
    """Delete guest users' transactions older than N days. Superuser only."""
    return await cleanup_guest_data_impl(days)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def decode_mcp_token(token: str) -> Optional[tuple[str, str]]:
    """Decode base64(username:password) → (username, password) or None."""
    if not token:
        return None
    try:
        decoded = base64.b64decode(token.encode()).decode()
    except Exception:
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return (username, password) if username else None


async def authenticate_for_mcp(db, username: str, password: str) -> Optional[User]:
    """Return User if credentials valid, else None."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not await verify_password(password, user.password):
        return None
    return user


# ---------------------------------------------------------------------------
# ASGI auth wrapper
# ---------------------------------------------------------------------------

async def _send_json_error(send, status: int, error: str) -> None:
    body = json.dumps({"error": error}).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


def create_mcp_asgi_app(inner_app=None):
    """
    Returns an ASGI app that handles /mcp/{base64token} paths directly.
    Receives the full unmodified path (via MCPMiddleware, not app.mount),
    so no prefix stripping or root_path mutation occurs.
    """
    if inner_app is None:
        inner_app = mcp.streamable_http_app()

    async def auth_wrapper(scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1003})
            return
        if scope["type"] != "http":
            return None

        path = scope.get("path", "")

        # Expect /mcp/{token} — extract token segment
        if not path.startswith("/mcp/"):
            await _send_json_error(send, 401, "Token required — use /mcp/<base64(username:password)>")
            return

        token = path[5:].split("/")[0]  # strip "/mcp/" then take first segment
        creds = decode_mcp_token(token)
        if not creds:
            await _send_json_error(send, 401, "Invalid token format")
            return

        username, password = creds
        db = SessionLocal()
        try:
            user = await authenticate_for_mcp(db, username, password)
            if not user:
                await _send_json_error(send, 401, "Invalid credentials")
                return

            # Set per-request context vars
            user_token = _current_user_var.set(user)
            db_token = _current_db_var.set(db)
            try:
                # Rewrite to /mcp — FastMCP route registered without trailing slash
                new_scope = {**scope, "path": "/mcp", "raw_path": b"/mcp"}
                await inner_app(new_scope, receive, send)
            finally:
                _current_user_var.reset(user_token)
                _current_db_var.reset(db_token)
        finally:
            db.close()

    return auth_wrapper


# ASGI app to mount in FastAPI at /mcp
mcp_asgi_app = create_mcp_asgi_app()
