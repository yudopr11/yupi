"""MCP tool implementations — call DB/services directly, no HTTP."""
import mimetypes
import uuid
from app.utils.uuid import uuid7
from datetime import datetime, UTC
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from openai import OpenAI
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.mcp.context import _current_db_var, _current_user_var
from app.models.auth import User
from app.models.blog import Post
from app.models.cuan import (
    Transaction,
    TransactionType,
    TrxAccountType,
    TrxCategory,
)
from app.utils.auth import get_password_hash
from app.utils.blog_helpers import (
    calculate_reading_time,
    generate_post_content,
    generate_post_embedding,
    generate_slug,
    search_posts_by_embedding,
)
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
    balance = a.get("balance") if isinstance(a, dict) else getattr(a, "balance", None)
    if isinstance(a, dict):
        return {
            "id": str(a["id"]),
            "name": a["name"],
            "type": a["type"].value if hasattr(a["type"], "value") else a["type"],
            "description": a.get("description"),
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
        "transfer_fee": float(t.transfer_fee) if t.transfer_fee else None,
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
    if not _user().is_superuser:
        raise PermissionError("Superuser required")
    db = _db()
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_serialize_user(u) for u in users]


async def register_user_impl(
    username: str,
    email: str,
    password: str,
    is_superuser: bool = False,
) -> dict:
    if not _user().is_superuser:
        raise PermissionError("Superuser required")
    db = _db()
    if db.query(User).filter(User.username == username).first():
        raise ValueError("Username already taken")
    if db.query(User).filter(User.email == email).first():
        raise ValueError("Email already taken")
    new_user = User(
        username=username,
        email=email,
        password=get_password_hash(password),
        is_superuser=is_superuser,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return _serialize_user(new_user)


async def delete_user_impl(user_id: str) -> dict:
    if not _user().is_superuser:
        raise PermissionError("Superuser required")
    db = _db()
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise LookupError(f"User {user_id} not found")
    if str(target.id) == str(_user().id):
        raise PermissionError("Cannot delete your own account")
    info = {"id": str(target.id), "username": target.username, "email": target.email}
    db.delete(target)
    db.commit()
    return {"message": f"User {user_id} deleted", "deleted_item": info}


# ---------------------------------------------------------------------------
# BLOG TOOLS
# ---------------------------------------------------------------------------

async def list_posts_impl(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    published_status: str = "published",
    use_rag: bool = False,
) -> dict:
    db = _db()
    query = db.query(Post)

    if published_status == "published":
        query = query.filter(Post.published == True)
    elif published_status == "unpublished":
        query = query.filter(Post.published == False)

    if tag:
        query = query.filter(Post.tags.contains([tag]))

    if search and use_rag:
        posts = search_posts_by_embedding(query=search, db=db, limit=limit, published_only=(published_status == "published"))
        return {"data": [_serialize_post(p) for p in posts], "total_count": len(posts), "has_more": False, "skip": skip, "limit": limit}

    if search:
        query = query.filter(
            or_(Post.title.ilike(f"%{search}%"), Post.content.ilike(f"%{search}%"), Post.excerpt.ilike(f"%{search}%"))
        )

    total = query.count()
    posts = query.order_by(Post.created_at.desc()).offset(skip).limit(limit + 1).all()
    has_more = len(posts) > limit
    return {
        "data": [_serialize_post(p) for p in posts[:limit]],
        "total_count": total,
        "has_more": has_more,
        "skip": skip,
        "limit": limit,
    }


async def get_post_impl(slug: str) -> dict:
    db = _db()
    post = db.query(Post).filter(Post.slug == slug).first()
    if not post:
        raise LookupError(f"Post '{slug}' not found")
    return _serialize_post(post)


async def create_post_impl(
    title: str,
    content: str,
    published: bool = False,
    tags: Optional[list] = None,
    excerpt: Optional[str] = None,
) -> dict:
    user = _user()
    if user.username == "guest":
        raise PermissionError("Guest users cannot create posts")
    db = _db()

    generated = generate_post_content(title, content, existing_tags=tags, need_excerpt=(excerpt is None))
    final_tags = tags if tags is not None else generated.get("tags", [])
    final_excerpt = excerpt if excerpt is not None else generated.get("excerpt", "")

    slug = generate_slug(title)
    existing = db.query(Post).filter(Post.slug == slug).first()
    if existing:
        slug = f"{slug}-{uuid7().hex[:6]}"

    post = Post(
        id=uuid7(),
        title=title,
        slug=slug,
        content=content,
        excerpt=final_excerpt,
        tags=final_tags,
        published=published,
        reading_time=calculate_reading_time(content),
        user_id=user.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    post.embedding = generate_post_embedding(post.title, post.excerpt)
    db.commit()
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
    user = _user()
    db = _db()
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise LookupError(f"Post {post_id} not found")
    if str(post.user_id) != str(user.id) and not user.is_superuser:
        raise PermissionError("Only the author or superuser can update this post")

    generated = generate_post_content(title, content, existing_tags=tags, need_excerpt=(excerpt is None), need_tags=(tags is None))
    post.title = title
    post.content = content
    post.published = published
    post.tags = tags if tags is not None else generated.get("tags", [])
    post.excerpt = excerpt if excerpt is not None else generated.get("excerpt", "")
    post.reading_time = calculate_reading_time(content)

    slug = generate_slug(title)
    existing = db.query(Post).filter(Post.slug == slug, Post.id != post.id).first()
    post.slug = f"{slug}-{uuid7().hex[:6]}" if existing else slug

    db.commit()
    db.refresh(post)
    post.embedding = generate_post_embedding(post.title, post.excerpt)
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


async def delete_post_impl(post_id: str) -> dict:
    user = _user()
    if not user.is_superuser:
        raise PermissionError("Superuser required")
    db = _db()
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise LookupError(f"Post {post_id} not found")
    info = {"id": str(post.id), "title": post.title}
    db.delete(post)
    db.commit()
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
    if user.username == "guest":
        raise PermissionError("Guest users cannot create accounts")
    db = _db()
    data = {"name": name, "type": type, "description": description, "limit": limit, "account_number": account_number}
    account = prepare_account_for_db(data, user.id)
    db.add(account)
    db.commit()
    db.refresh(account)

    if account.type == TrxAccountType.CREDIT_CARD and account.limit is not None:
        create_credit_card_initial_transaction(db, account, user.id)

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
    if user.username == "guest":
        raise PermissionError("Guest users cannot update accounts")
    db = _db()
    account = validate_account(db, uuid.UUID(account_id), user.id)
    if type == TrxAccountType.CREDIT_CARD.value and limit is None:
        raise HTTPException(status_code=400, detail="Credit card accounts must have a limit.")
    if type != TrxAccountType.CREDIT_CARD.value and limit is not None:
        raise HTTPException(status_code=400, detail=f"Account type '{type}' cannot have a limit.")
    account.name = name
    account.type = type
    account.description = description
    account.limit = limit
    account.account_number = account_number
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


async def delete_account_impl(account_id: str) -> dict:
    user = _user()
    if user.username == "guest":
        raise PermissionError("Guest users cannot delete accounts")
    db = _db()
    account = validate_account(db, uuid.UUID(account_id), user.id)
    deleted_info = prepare_deleted_account_info(account)
    db.delete(account)
    db.commit()
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
    if user.username == "guest":
        raise PermissionError("Guest users cannot create categories")
    db = _db()
    cat = prepare_category_for_db({"name": name, "type": type}, user.id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _serialize_category(cat)


async def update_category_impl(category_id: str, name: str, type: str) -> dict:
    user = _user()
    if user.username == "guest":
        raise PermissionError("Guest users cannot update categories")
    db = _db()
    cat = validate_category(db, uuid.UUID(category_id), user.id)
    cat.name = name
    cat.type = type
    db.commit()
    db.refresh(cat)
    return _serialize_category(cat)


async def delete_category_impl(category_id: str) -> dict:
    user = _user()
    if user.username == "guest":
        raise PermissionError("Guest users cannot delete categories")
    db = _db()
    cat = validate_category(db, uuid.UUID(category_id), user.id)
    deleted_info = prepare_deleted_category_info(cat)
    db.delete(cat)
    db.commit()
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
) -> dict:
    db = _db()
    user = _user()
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
    txs = query.offset(skip).limit(limit + 1).all()
    has_more = len(txs) > limit
    return {
        "data": [_serialize_transaction(t) for t in txs[:limit]],
        "total_count": total,
        "has_more": has_more,
        "limit": limit,
        "skip": skip,
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
    if user.username == "guest":
        raise PermissionError("Guest users cannot create transactions")
    db = _db()
    aid = uuid.UUID(account_id)
    cid = uuid.UUID(category_id) if category_id else None
    did = uuid.UUID(destination_account_id) if destination_account_id else None
    tx_type = TransactionType(transaction_type.lower())

    account = validate_account(db, aid, user.id)
    category = validate_category(db, cid, user.id)
    validate_transaction_category_match(tx_type, category)
    validate_transfer(tx_type, did, aid, Decimal(str(transfer_fee or 0)), db, user.id)

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
    db.commit()
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
    if user.username == "guest":
        raise PermissionError("Guest users cannot update transactions")
    db = _db()
    tid = uuid.UUID(transaction_id)
    tx = db.query(Transaction).filter(Transaction.id == tid, Transaction.user_id == user.id).first()
    if not tx:
        raise LookupError(f"Transaction {transaction_id} not found")

    aid = uuid.UUID(account_id)
    cid = uuid.UUID(category_id) if category_id else None
    did = uuid.UUID(destination_account_id) if destination_account_id else None
    tx_type = TransactionType(transaction_type.lower())

    validate_account(db, aid, user.id)
    category = validate_category(db, cid, user.id)
    validate_transaction_category_match(tx_type, category)
    validate_transfer(tx_type, did, aid, Decimal(str(transfer_fee or 0)), db, user.id)

    tx.transaction_date = datetime.fromisoformat(transaction_date)
    tx.description = description
    tx.amount = amount
    tx.transaction_type = tx_type
    tx.account_id = aid
    tx.category_id = cid
    tx.destination_account_id = did
    tx.transfer_fee = Decimal(str(transfer_fee)) if transfer_fee else Decimal("0")
    db.commit()
    db.refresh(tx)
    return _serialize_transaction(tx)


async def delete_transaction_impl(transaction_id: str) -> dict:
    user = _user()
    if user.username == "guest":
        raise PermissionError("Guest users cannot delete transactions")
    db = _db()
    tid = uuid.UUID(transaction_id)
    tx = db.query(Transaction).filter(Transaction.id == tid, Transaction.user_id == user.id).first()
    if not tx:
        raise LookupError(f"Transaction {transaction_id} not found")
    deleted_info = prepare_deleted_transaction_info(tx)
    db.query(Transaction).filter(Transaction.id == tid).delete()
    db.commit()
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

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    if mime not in {"image/jpeg", "image/png", "image/jpg", "image/webp"}:
        raise ValueError(f"Unsupported image type: {mime}")

    image_bytes = path.read_bytes()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError("Image exceeds 5MB limit")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    b64_image = _b64.b64encode(image_bytes).decode()

    if not image_description:
        vision_resp = client.chat.completions.create(
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

    analysis_resp = client.chat.completions.create(
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
