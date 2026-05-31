"""MCP tool implementations — call DB/services directly, no HTTP."""
import asyncio
import mimetypes
import uuid
from datetime import datetime, UTC
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import desc, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.mcp.context import _current_db_var, _current_user_var
from app.models.auth import User
from app.models.blog import Post
from app.models.cuan import (
    Transaction,
    TransactionType,
    TrxAccountType,
    TrxCategory,
)
from app.models.file import FileUpload
from app.utils.auth import get_password_hash
from app.utils.blog_helpers import (
    _get_openai_client,
    calculate_reading_time,
    generate_post_content,
    generate_post_embedding,
    generate_slug,
    search_posts_by_embedding,
)
from app.utils.common import escape_like
from app.utils.cuan_helpers import (
    calculate_account_balance,
    calculate_date_range,
    create_credit_card_initial_transaction,
    get_accounts_with_balance,
    get_filtered_categories,
    get_filtered_transactions,
    get_year_end,
    prepare_account_for_db,
    prepare_category_for_db,
    prepare_deleted_account_info,
    prepare_deleted_category_info,
    prepare_deleted_transaction_info,
    prepare_transaction_for_db,
    validate_account,
    validate_category,
    validate_transaction_category_match,
    validate_transfer,
)


def _user() -> User:
    return _current_user_var.get()


def _db() -> Session:
    return _current_db_var.get()


def _require_superuser():
    """Match get_non_guest_superuser: superuser + not guest."""
    user = _user()
    if not user.is_superuser or user.username == "guest":
        raise PermissionError("Superuser required")


def _require_not_guest():
    """Match get_non_guest_user: authenticated + not guest."""
    if _user().username == "guest":
        raise PermissionError("Guest users not allowed")


def _serialize_user(u: User) -> dict:
    return {
        "id": str(u.id),
        "username": u.username,
        "email": u.email,
        "is_superuser": u.is_superuser,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


def _serialize_account(a) -> dict:
    if isinstance(a, dict):
        return {
            "id": str(a["id"]),
            "name": a["name"],
            "type": a["type"].value if hasattr(a["type"], "value") else a["type"],
            "description": a.get("description"),
            "account_number": a.get("account_number"),
            "limit": float(a["limit"]) if a.get("limit") is not None else None,
            "balance": float(a["balance"]) if a.get("balance") is not None else None,
            "total_income": float(a.get("total_income", 0)),
            "total_expenses": float(a.get("total_expenses", 0)),
            "total_transfers_in": float(a.get("total_transfers_in", 0)),
            "total_transfers_out": float(a.get("total_transfers_out", 0)),
            "total_transfer_fees": float(a.get("total_transfer_fees", 0)),
            "payable_balance": float(a["payable_balance"]) if a.get("payable_balance") is not None else None,
        }
    return {
        "id": str(a.id),
        "name": a.name,
        "type": a.type.value if hasattr(a.type, "value") else a.type,
        "description": a.description,
        "limit": float(a.limit) if a.limit is not None else None,
        "account_number": a.account_number,
    }


def _serialize_category(c: TrxCategory) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "type": c.type.value if hasattr(c.type, "value") else c.type,
        "user_id": str(c.user_id),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _serialize_transaction(t: Transaction) -> dict:
    return {
        "id": str(t.id),
        "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
        "description": t.description,
        "amount": float(t.amount),
        "transaction_type": t.transaction_type.value if hasattr(t.transaction_type, "value") else t.transaction_type,
        "account_id": str(t.account_id),
        "category_id": str(t.category_id) if t.category_id else None,
        "destination_account_id": str(t.destination_account_id) if t.destination_account_id else None,
        "transfer_fee": float(t.transfer_fee) if t.transfer_fee is not None else None,
        "receipt_file_id": str(t.receipt_file_id) if t.receipt_file_id else None,
        "receipt_url": t.receipt_url,
        "user_id": str(t.user_id),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _serialize_post(p: Post) -> dict:
    return {
        "id": str(p.id),
        "title": p.title,
        "slug": p.slug,
        "content": p.content,
        "excerpt": p.excerpt,
        "tags": p.tags,
        "published": p.published,
        "reading_time": p.reading_time,
        "user_id": str(p.user_id),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ---------------------------------------------------------------------------
# AUTH TOOLS
# ---------------------------------------------------------------------------

async def get_current_user_impl() -> dict:
    return _serialize_user(_user())


async def list_all_users_impl() -> list:
    _require_superuser()
    db = _db()
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_serialize_user(u) for u in users]


async def register_user_impl(
    username: str,
    email: str,
    password: str,
    is_superuser: bool = False,
) -> dict:
    _require_superuser()
    db = _db()
    if db.query(User).filter(User.username == username).first():
        raise ValueError("Username already taken")
    if db.query(User).filter(User.email == email).first():
        raise ValueError("Email already taken")
    new_user = User(
        username=username,
        email=email,
        password=await get_password_hash(password),
        is_superuser=is_superuser,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(new_user)
    return _serialize_user(new_user)


async def delete_user_impl(user_id: str) -> dict:
    _require_superuser()
    db = _db()
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise LookupError(f"User {user_id} not found")
    if str(target.id) == str(_user().id):
        raise PermissionError("Cannot delete your own account")
    info = {"id": str(target.id), "username": target.username, "email": target.email}
    db.delete(target)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {"message": f"User {user_id} deleted", "deleted_item": info}


# ---------------------------------------------------------------------------
# BLOG TOOLS
# ---------------------------------------------------------------------------

async def list_posts_impl(
    skip: int = 0,
    limit: int = 10,
    cursor: Optional[str] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    published_status: str = "published",
    use_rag: bool = False,
) -> dict:
    db = _db()
    limit = min(limit, 100)

    # Non-superusers can only see published posts
    user = _user()
    if not user.is_superuser:
        published_status = "published"

    # RAG semantic search path
    if search and use_rag:
        is_published_only = published_status == "published"
        similarity_threshold = 0.3
        vector_results = await asyncio.to_thread(
            search_posts_by_embedding,
            query=search, db=db, limit=100,
            similarity_threshold=similarity_threshold,
            published_only=is_published_only,
        )

        # Filter unpublished if requested
        if published_status == "unpublished":
            vector_results = [p for p in vector_results if not p["published"]]

        # Filter by tag (case-insensitive)
        if tag:
            vector_results = [
                p for p in vector_results
                if p["tags"] and any(t.lower() == tag.lower() for t in p["tags"])
            ]

        total_count = len(vector_results)

        # Cursor pagination
        next_cursor = None
        if cursor:
            from datetime import datetime as dt
            cursor_dt = dt.fromisoformat(cursor)
            vector_results = [p for p in vector_results if p["created_at"] and p["created_at"] < cursor_dt]
            skip = 0

        paginated = vector_results[:limit + 1]
        has_more = len(paginated) > limit
        if has_more:
            paginated = paginated[:limit]
            last = paginated[-1]
            created = last.get("created_at")
            next_cursor = created.isoformat() if hasattr(created, "isoformat") else (created if isinstance(created, str) else None)

        return {
            "items": paginated,
            "total_count": total_count,
            "has_more": has_more,
            "limit": limit,
            "skip": skip,
            "next_cursor": next_cursor,
        }

    # SQL search path
    query = db.query(Post)

    if published_status == "published":
        query = query.filter(Post.published == True)
    elif published_status == "unpublished":
        query = query.filter(Post.published == False)

    if search:
        escaped = escape_like(search)
        query = query.filter(
            or_(
                Post.title.ilike(f"%{escaped}%", escape="\\"),
                Post.excerpt.ilike(f"%{escaped}%", escape="\\"),
                Post.content.ilike(f"%{escaped}%", escape="\\"),
                func.array_to_string(Post.tags, ',').ilike(f"%{escaped}%", escape="\\"),
            )
        )

    if tag:
        query = query.filter(func.lower(func.array_to_string(Post.tags, ',', '')).contains(func.lower(escape_like(tag))))

    total = query.count()

    # Cursor pagination (cursor replaces skip)
    next_cursor = None
    if cursor:
        from datetime import datetime as dt
        cursor_dt = dt.fromisoformat(cursor)
        query = query.filter(Post.created_at < cursor_dt)
        skip = 0

    posts = query.order_by(Post.created_at.desc()).offset(skip).limit(limit + 1).all()
    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]
        next_cursor = posts[-1].created_at.isoformat() if posts else None

    return {
        "items": [_serialize_post(p) for p in posts],
        "total_count": total,
        "has_more": has_more,
        "limit": limit,
        "skip": skip,
        "next_cursor": next_cursor,
    }


async def get_post_impl(slug: str) -> dict:
    db = _db()
    post = db.query(Post).filter(Post.slug == slug).first()
    if not post:
        raise LookupError(f"Post '{slug}' not found")
    if not post.published and not _user().is_superuser:
        raise LookupError("Post not found")
    return _serialize_post(post)


async def create_post_impl(
    title: str,
    content: str,
    published: bool = False,
    tags: Optional[list] = None,
    excerpt: Optional[str] = None,
) -> dict:
    _require_superuser()
    db = _db()

    need_excerpt = not excerpt or excerpt.strip() == ""
    need_tags = not tags or len(tags) == 0

    existing_tags = []
    if need_tags:
        existing_tags = [t[0] for t in db.query(func.unnest(Post.tags)).distinct().all()]

    generated = await asyncio.to_thread(
        generate_post_content,
        title, content,
        existing_tags=existing_tags,
        need_excerpt=need_excerpt,
        need_tags=need_tags,
    )
    if need_tags and generated.get("tags"):
        tags = generated["tags"]
    final_tags = tags if tags is not None else generated.get("tags", [])
    final_excerpt = excerpt if not need_excerpt else generated.get("excerpt", "")

    slug = generate_slug(title)
    base_slug = slug
    for counter in range(1, 101):
        if not db.query(Post).filter(Post.slug == slug).first():
            break
        slug = f"{base_slug}-{counter}"
    else:
        raise RuntimeError("Could not generate unique slug")

    post = Post(
        title=title,
        slug=slug,
        content=content,
        excerpt=final_excerpt,
        tags=final_tags,
        published=published,
        reading_time=calculate_reading_time(content),
        user_id=_user().id,
    )
    db.add(post)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(post)

    if post.excerpt:
        post.embedding = await asyncio.to_thread(generate_post_embedding, post.title, post.excerpt)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        db.refresh(post)

    return _serialize_post(post)


async def update_post_impl(
    post_id: str,
    title: str,
    content: str,
    published: bool = False,
    tags: Optional[list] = None,
    excerpt: Optional[str] = None,
) -> dict:
    _require_superuser()
    db = _db()
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise LookupError(f"Post {post_id} not found")

    need_excerpt = not excerpt or excerpt.strip() == ""
    need_tags = not tags or len(tags) == 0

    existing_tags = []
    if need_tags:
        existing_tags = [t[0] for t in db.query(func.unnest(Post.tags)).distinct().all()]

    if need_excerpt or need_tags:
        generated = await asyncio.to_thread(
            generate_post_content,
            title, content,
            existing_tags=existing_tags,
            need_excerpt=need_excerpt,
            need_tags=need_tags,
        )
        if need_excerpt and generated.get("excerpt"):
            excerpt = generated["excerpt"]
        if need_tags and generated.get("tags"):
            tags = generated["tags"]

    # Update all fields
    post_data = {
        "title": title,
        "content": content,
        "published": published,
        "tags": tags if tags is not None else post.tags,
        "excerpt": excerpt if excerpt is not None else post.excerpt,
    }
    for key, value in post_data.items():
        setattr(post, key, value)

    if title:
        slug = generate_slug(title)
        base_slug = slug
        for counter in range(1, 101):
            if not db.query(Post).filter(Post.slug == slug, Post.id != post.id).first():
                break
            slug = f"{base_slug}-{counter}"
        else:
            raise RuntimeError("Could not generate unique slug")
        post.slug = slug
    if content:
        post.reading_time = calculate_reading_time(content)
    if title or excerpt is not None:
        post.embedding = await asyncio.to_thread(generate_post_embedding, post.title, post.excerpt)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(post)
    return _serialize_post(post)


async def delete_post_impl(post_id: str) -> dict:
    _require_superuser()
    db = _db()
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise LookupError(f"Post {post_id} not found")
    info = {"id": str(post.id), "uuid": str(post.id), "title": post.title}
    db.delete(post)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {"message": f"Post {post_id} deleted", "deleted_item": info}


# ---------------------------------------------------------------------------
# CUAN — ACCOUNTS
# ---------------------------------------------------------------------------

async def list_accounts_impl(
    account_type: Optional[str] = None,
    year: Optional[int] = None,
) -> list:
    db = _db()
    user = _user()
    as_of = get_year_end(year) if year is not None else None
    accounts = get_accounts_with_balance(db, user.id, account_type, as_of=as_of)
    return [_serialize_account(a) for a in accounts]


async def get_account_balance_impl(account_id: str, year: Optional[int] = None) -> dict:
    db = _db()
    user = _user()
    aid = uuid.UUID(account_id)
    validate_account(db, aid, user.id)
    as_of = get_year_end(year) if year is not None else None
    details = calculate_account_balance(db, aid, user.id, as_of=as_of)
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in details.items()}


async def create_account_impl(
    name: str,
    type: str,
    description: Optional[str] = None,
    limit: Optional[float] = None,
    account_number: Optional[str] = None,
) -> dict:
    user = _user()
    db = _db()
    data = {"name": name, "type": type, "description": description, "limit": limit, "account_number": account_number}
    account = prepare_account_for_db(data, user.id)
    db.add(account)
    db.flush()  # Get account.id without committing

    if account.type == TrxAccountType.CREDIT_CARD and account.limit is not None:
        create_credit_card_initial_transaction(db, account, user.id)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(account)

    return _serialize_account(account)


async def update_account_impl(
    account_id: str,
    name: str,
    type: str,
    description: Optional[str] = None,
    limit: Optional[float] = None,
    account_number: Optional[str] = None,
) -> dict:
    user = _user()
    db = _db()
    account = validate_account(db, uuid.UUID(account_id), user.id)
    if type == TrxAccountType.CREDIT_CARD.value and limit is None:
        raise ValueError("Credit card accounts must have a limit.")
    if type != TrxAccountType.CREDIT_CARD.value and limit is not None:
        raise ValueError(f"Account type '{type}' cannot have a limit.")
    account.name = name
    account.type = type
    account.description = description
    account.limit = limit
    account.account_number = account_number
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(account)
    return _serialize_account(account)


async def delete_account_impl(account_id: str) -> dict:
    user = _user()
    db = _db()
    account = validate_account(db, uuid.UUID(account_id), user.id)
    deleted_info = prepare_deleted_account_info(account)
    db.delete(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {"message": f"Account {account_id} deleted", "deleted_item": deleted_info}


# ---------------------------------------------------------------------------
# CUAN — CATEGORIES
# ---------------------------------------------------------------------------

async def list_categories_impl(category_type: Optional[str] = None) -> list:
    db = _db()
    user = _user()
    cats = get_filtered_categories(db, user.id, category_type)
    return [_serialize_category(c) for c in cats]


async def create_category_impl(name: str, type: str) -> dict:
    user = _user()
    db = _db()
    cat = prepare_category_for_db({"name": name, "type": type}, user.id)
    db.add(cat)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(cat)
    return _serialize_category(cat)


async def update_category_impl(category_id: str, name: str, type: str) -> dict:
    user = _user()
    db = _db()
    cat = validate_category(db, uuid.UUID(category_id), user.id)
    cat.name = name
    cat.type = type
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(cat)
    return _serialize_category(cat)


async def delete_category_impl(category_id: str) -> dict:
    user = _user()
    db = _db()
    cat = validate_category(db, uuid.UUID(category_id), user.id)
    deleted_info = prepare_deleted_category_info(cat)
    db.delete(cat)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {"message": f"Category {category_id} deleted", "deleted_item": deleted_info}


# ---------------------------------------------------------------------------
# CUAN — TRANSACTIONS
# ---------------------------------------------------------------------------

async def list_transactions_impl(
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
    db = _db()
    user = _user()
    limit = min(limit, 100)
    parsed_start = datetime.fromisoformat(start_date) if start_date else None
    parsed_end = datetime.fromisoformat(end_date) if end_date else None
    query = get_filtered_transactions(
        db=db,
        user_id=user.id,
        account_name=account_name,
        category_name=category_name,
        transaction_type=transaction_type,
        start_date=parsed_start,
        end_date=parsed_end,
        date_filter_type=date_filter_type,
        timezone=timezone,
        order_by=order_by,
        sort_order=sort_order,
        return_query=True,
    )
    total = query.count()

    # Cursor-based pagination (cursor replaces skip)
    next_cursor = None
    if cursor:
        cursor_dt = datetime.fromisoformat(cursor)
        if sort_order.lower() == "desc":
            query = query.filter(Transaction.created_at < cursor_dt)
        else:
            query = query.filter(Transaction.created_at > cursor_dt)
        skip = 0  # cursor replaces offset

    txs = query.offset(skip).limit(limit + 1).all()
    has_more = len(txs) > limit
    if has_more:
        txs = txs[:limit]
        next_cursor = txs[-1].created_at.isoformat()

    return {
        "data": [_serialize_transaction(t) for t in txs],
        "total_count": total,
        "has_more": has_more,
        "limit": limit,
        "skip": skip,
        "next_cursor": next_cursor,
    }


async def create_transaction_impl(
    transaction_date: str,
    description: str,
    amount: float,
    transaction_type: str,
    account_id: str,
    category_id: Optional[str] = None,
    destination_account_id: Optional[str] = None,
    transfer_fee: Optional[float] = None,
) -> dict:
    user = _user()
    db = _db()
    aid = uuid.UUID(account_id)
    cid = uuid.UUID(category_id) if category_id else None
    did = uuid.UUID(destination_account_id) if destination_account_id else None
    tx_type = TransactionType(transaction_type.lower())

    account = validate_account(db, aid, user.id)
    category = validate_category(db, cid, user.id)
    validate_transaction_category_match(tx_type, category)
    validate_transfer(tx_type, did, aid, Decimal(str(transfer_fee or 0)), db, user.id)

    # Credit card balance check (matches API router)
    if tx_type == TransactionType.EXPENSE and account.type == TrxAccountType.CREDIT_CARD:
        balance_details = calculate_account_balance(db, aid, user.id)
        if balance_details["balance"] <= 0:
            raise ValueError("Cannot create expense with this credit card - no available balance. Please top up by creating a transfer to this account.")

    data = {
        "transaction_date": datetime.fromisoformat(transaction_date),
        "description": description,
        "amount": amount,
        "transaction_type": tx_type,
        "account_id": aid,
        "category_id": cid,
        "destination_account_id": did,
        "transfer_fee": Decimal(str(transfer_fee)) if transfer_fee else Decimal("0"),
    }
    tx = prepare_transaction_for_db(data, user.id)
    db.add(tx)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(tx)
    return _serialize_transaction(tx)


async def update_transaction_impl(
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
    user = _user()
    db = _db()
    tid = uuid.UUID(transaction_id)
    tx = db.query(Transaction).filter(Transaction.id == tid, Transaction.user_id == user.id).first()
    if not tx:
        raise LookupError(f"Transaction {transaction_id} not found")

    aid = uuid.UUID(account_id)
    cid = uuid.UUID(category_id) if category_id else None
    did = uuid.UUID(destination_account_id) if destination_account_id else None
    tx_type = TransactionType(transaction_type.lower())

    account = validate_account(db, aid, user.id)
    category = validate_category(db, cid, user.id)
    validate_transaction_category_match(tx_type, category)
    validate_transfer(tx_type, did, aid, Decimal(str(transfer_fee or 0)), db, user.id)

    # Credit card balance check (matches API router)
    if (
        tx_type == TransactionType.EXPENSE
        and account.type == TrxAccountType.CREDIT_CARD
        and (tx.transaction_type != TransactionType.EXPENSE or amount > float(tx.amount))
    ):
        balance_details = calculate_account_balance(db, aid, user.id)
        adjusted_balance = balance_details["balance"]
        if tx.transaction_type == TransactionType.EXPENSE and tx.account_id == aid:
            adjusted_balance += float(tx.amount)
        if adjusted_balance - amount < 0:
            raise ValueError("Insufficient credit card balance for this update. Please top up the account.")

    tx.transaction_date = datetime.fromisoformat(transaction_date)
    tx.description = description
    tx.amount = amount
    tx.transaction_type = tx_type
    tx.account_id = aid
    tx.category_id = cid
    tx.destination_account_id = did
    tx.transfer_fee = Decimal(str(transfer_fee)) if transfer_fee else Decimal("0")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(tx)
    return _serialize_transaction(tx)


async def delete_transaction_impl(transaction_id: str) -> dict:
    user = _user()
    db = _db()
    tid = uuid.UUID(transaction_id)
    tx = db.query(Transaction).filter(Transaction.id == tid, Transaction.user_id == user.id).first()
    if not tx:
        raise LookupError(f"Transaction {transaction_id} not found")
    deleted_info = prepare_deleted_transaction_info(tx)
    db.query(Transaction).filter(Transaction.id == tid, Transaction.user_id == user.id).delete()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {"message": f"Transaction {transaction_id} deleted", "deleted_item": deleted_info}


# ---------------------------------------------------------------------------
# CUAN — STATISTICS
# ---------------------------------------------------------------------------

async def get_financial_summary_impl(
    period: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timezone: str = "UTC",
) -> dict:
    db = _db()
    user = _user()
    if start_date and end_date:
        sd = datetime.fromisoformat(start_date)
        ed = datetime.fromisoformat(end_date)
    else:
        sd, ed = calculate_date_range(period, timezone)

    results = db.query(
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total"),
    ).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_date.between(sd, ed),
    ).group_by(Transaction.transaction_type).all()

    summary = {"income": 0.0, "expense": 0.0, "transfer": 0.0}
    for tt, total in results:
        if tt.value in summary:
            summary[tt.value] = float(total)
    summary["net"] = summary["income"] - summary["expense"]

    return {
        "period": {"start_date": sd.isoformat(), "end_date": ed.isoformat(), "period_type": period},
        "totals": summary,
    }


async def get_category_distribution_impl(
    transaction_type: str = "expense",
    period: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timezone: str = "UTC",
) -> dict:
    db = _db()
    user = _user()
    if start_date and end_date:
        sd = datetime.fromisoformat(start_date)
        ed = datetime.fromisoformat(end_date)
    else:
        sd, ed = calculate_date_range(period, timezone)

    tx_type = TransactionType(transaction_type)
    results = db.query(
        func.coalesce(TrxCategory.name, "Uncategorized").label("name"),
        TrxCategory.id.label("id"),
        func.sum(Transaction.amount).label("total"),
    ).outerjoin(TrxCategory, Transaction.category_id == TrxCategory.id).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_date.between(sd, ed),
        Transaction.transaction_type == tx_type,
    ).group_by(TrxCategory.id, TrxCategory.name).order_by(desc("total")).all()

    grand_total = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_date.between(sd, ed),
        Transaction.transaction_type == tx_type,
    ).scalar() or Decimal("0")
    grand_total_f = float(grand_total)

    categories = [
        {
            "name": name,
            "id": str(id) if id else None,
            "total": float(total),
            "percentage": float(total / grand_total * 100) if grand_total > 0 else 0,
        }
        for name, id, total in results
    ]
    return {
        "period": {"start_date": sd.isoformat(), "end_date": ed.isoformat(), "period_type": period},
        "transaction_type": transaction_type,
        "total": grand_total_f,
        "categories": categories,
    }


async def get_trends_impl(
    period: str = "month",
    group_by: str = "day",
    transaction_types: Optional[list] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timezone: str = "UTC",
) -> dict:
    db = _db()
    user = _user()
    if start_date and end_date:
        sd = datetime.fromisoformat(start_date)
        ed = datetime.fromisoformat(end_date)
    else:
        sd, ed = calculate_date_range(period, timezone)

    tx_types = transaction_types or ["income", "expense"]
    date_trunc = func.date_trunc(group_by, Transaction.transaction_date)
    results = db.query(
        date_trunc.label("date"),
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total"),
    ).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_date.between(sd, ed),
        Transaction.transaction_type.in_(tx_types),
    ).group_by(date_trunc, Transaction.transaction_type).order_by(date_trunc).all()

    date_fmt = "%Y-%m-%dT%H:00:00" if group_by == "hour" else "%Y-%m-%d"
    trends: dict = {}
    for date, tx_type, total in results:
        ds = date.strftime(date_fmt)
        if ds not in trends:
            trends[ds] = {"date": ds, "income": 0.0, "expense": 0.0, "transfer": 0.0, "net": 0.0}
        trends[ds][tx_type.value] = float(total)
        trends[ds]["net"] = trends[ds]["income"] - trends[ds]["expense"]

    return {
        "period": {"start_date": sd.isoformat(), "end_date": ed.isoformat(), "period_type": period, "group_by": group_by},
        "trends": list(trends.values()),
    }


async def get_account_summary_impl() -> dict:
    db = _db()
    user = _user()
    accounts = get_accounts_with_balance(db, user.id)
    total_balance = sum(float(a.get("balance", 0) or 0) for a in accounts)
    total_limit = sum(float(a.get("limit", 0) or 0) for a in accounts if a.get("type") == TrxAccountType.CREDIT_CARD or (hasattr(a.get("type"), "value") and a["type"].value == "credit_card"))
    return {
        "total_balance": total_balance,
        "total_credit_limit": total_limit,
        "accounts": [_serialize_account(a) for a in accounts],
    }


# ---------------------------------------------------------------------------
# NGAKAK — BILL SPLIT
# ---------------------------------------------------------------------------

async def analyze_bill_impl(
    image_path: str,
    description: str,
    image_description: Optional[str] = None,
) -> dict:
    import base64 as _b64
    import json

    path = Path(image_path).resolve()
    # Sandbox: only allow reading from /tmp or current working directory
    allowed_prefixes = [Path("/tmp").resolve(), Path.cwd().resolve()]
    if not any(path.resolve().is_relative_to(p) for p in allowed_prefixes):
        raise PermissionError(f"Path not allowed: {image_path}. Must be under /tmp or {Path.cwd()}")
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    if mime not in {"image/jpeg", "image/png", "image/jpg", "image/webp"}:
        raise ValueError(f"Unsupported image type: {mime}")

    image_bytes = path.read_bytes()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError("Image exceeds 5MB limit")

    client = _get_openai_client()
    b64_image = _b64.b64encode(image_bytes).decode()

    if not image_description:
        vision_resp = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this bill/receipt image. List all items with their prices, subtotal, taxes, service charges, and total. Be precise with numbers."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_image}"}},
                    ],
                }
            ],
        )
        image_description = vision_resp.choices[0].message.content

    analysis_resp = await asyncio.to_thread(
        client.chat.completions.create,
        model="o3-mini",
        messages=[
            {
                "role": "user",
                "content": f"""Bill details:\n{image_description}\n\nOrders:\n{description}\n\nSplit the bill fairly. Return JSON with keys: people (list of {{name, items, subtotal, tax_share, service_share, discount_share, total}}), grand_total, tax, service_charge, discount.""",
            }
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(analysis_resp.choices[0].message.content)


# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------

def _serialize_file(f: FileUpload) -> dict:
    return {
        "id": str(f.id),
        "filename": f.original_filename,
        "content_type": f.content_type,
        "size_bytes": f.size_bytes,
        "storage_key": f.storage_key,
        "is_orphan": f.is_orphan,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


async def list_files_impl(limit: int = 50) -> list:
    """List current user's uploaded files."""
    db = _db()
    user = _user()
    limit = min(limit, 100)
    files = (
        db.query(FileUpload)
        .filter(FileUpload.user_id == user.id, FileUpload.is_orphan == False)
        .order_by(desc(FileUpload.created_at))
        .limit(limit)
        .all()
    )
    return [_serialize_file(f) for f in files]


async def delete_file_impl(file_id: str) -> dict:
    """Mark a file as orphan (soft delete)."""
    from app.utils.file_service import mark_orphan

    db = _db()
    user = _user()
    query = db.query(FileUpload).filter(FileUpload.id == file_id)
    if not user.is_superuser:
        query = query.filter(FileUpload.user_id == user.id)
    file_upload = query.first()
    if not file_upload:
        raise ValueError(f"File {file_id} not found or access denied")

    mark_orphan(db, file_upload.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {"message": "File marked for deletion", "file_id": file_id}


async def cleanup_orphans_impl() -> dict:
    """Delete all orphaned files from storage and DB. Superuser only."""
    from app.utils.file_service import cleanup_orphans

    _require_superuser()
    db = _db()

    deleted = cleanup_orphans(db)
    return {"message": f"Cleaned up {len(deleted)} orphaned files", "deleted": deleted}


async def cleanup_guest_data_impl(days: int = 30) -> dict:
    """Delete guest users' transactions older than N days. Superuser only."""
    from datetime import timedelta
    from app.utils.file_service import mark_orphan, delete_file_from_storage

    if days < 1 or days > 365:
        raise ValueError("days must be between 1 and 365")

    _require_superuser()
    db = _db()

    cutoff = datetime.now(UTC) - timedelta(days=days)

    guest_users = db.query(User).filter(User.username == "guest").all()
    guest_ids = [u.id for u in guest_users]

    if not guest_ids:
        return {"message": "No guest users found", "deleted_transactions": 0, "orphaned_files": 0}

    old_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id.in_(guest_ids),
            Transaction.created_at < cutoff,
        )
        .all()
    )

    deleted_count = len(old_transactions)
    orphaned_files = 0
    receipt_files = []

    for tx in old_transactions:
        if tx.receipt_file_id:
            file_upload = mark_orphan(db, tx.receipt_file_id)
            if file_upload:
                receipt_files.append(file_upload)
            orphaned_files += 1
        db.delete(tx)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    for f in receipt_files:
        delete_file_from_storage(f.storage_key, f.bucket)

    return {
        "message": f"Cleaned up {deleted_count} guest transactions older than {days} days",
        "deleted_transactions": deleted_count,
        "orphaned_files": orphaned_files,
    }
