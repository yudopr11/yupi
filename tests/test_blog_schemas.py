"""Tests for app/schemas/blog.py and app/schemas/ngakak.py."""
from decimal import Decimal

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# PostCreate
# ---------------------------------------------------------------------------

def test_post_create_minimal_valid():
    from app.schemas.blog import PostCreate
    schema = PostCreate(title="Hello World", content="Some content here")
    assert schema.title == "Hello World"
    assert schema.published is False
    assert schema.tags is None
    assert schema.excerpt is None


def test_post_create_full_valid():
    from app.schemas.blog import PostCreate
    schema = PostCreate(
        title="Full Post",
        content="Long content",
        published=True,
        tags=["Python", "FastAPI"],
        excerpt="Short summary"
    )
    assert schema.published is True
    assert schema.tags == ["Python", "FastAPI"]


def test_post_create_missing_title_raises():
    from app.schemas.blog import PostCreate
    with pytest.raises(ValidationError):
        PostCreate(content="content only")


def test_post_create_missing_content_raises():
    from app.schemas.blog import PostCreate
    with pytest.raises(ValidationError):
        PostCreate(title="title only")


# ---------------------------------------------------------------------------
# PaginatedPostsResponse
# ---------------------------------------------------------------------------

def test_paginated_posts_response_empty():
    from app.schemas.blog import PaginatedPostsResponse
    schema = PaginatedPostsResponse(items=[], total_count=0, has_more=False, limit=10, skip=0)
    assert schema.total_count == 0
    assert schema.items == []


def test_paginated_posts_response_has_more():
    from app.schemas.blog import PaginatedPostsResponse
    schema = PaginatedPostsResponse(items=[], total_count=100, has_more=True, limit=10, skip=0)
    assert schema.has_more is True


def test_paginated_posts_response_next_cursor_default_none():
    from app.schemas.blog import PaginatedPostsResponse
    schema = PaginatedPostsResponse(items=[], total_count=0, has_more=False, limit=10, skip=0)
    assert schema.next_cursor is None


def test_paginated_posts_response_next_cursor_string():
    from app.schemas.blog import PaginatedPostsResponse
    schema = PaginatedPostsResponse(
        items=[], total_count=10, has_more=True, limit=10, skip=0,
        next_cursor="2026-02-11T16:13:03.135932Z"
    )
    assert schema.next_cursor == "2026-02-11T16:13:03.135932Z"


# ---------------------------------------------------------------------------
# PostBase validation
# ---------------------------------------------------------------------------

def test_post_base_title_too_long_raises():
    from app.schemas.blog import PostBase
    with pytest.raises(ValidationError):
        PostBase(title="x" * 201, content="some content")


def test_post_base_empty_title_raises():
    from app.schemas.blog import PostBase
    with pytest.raises(ValidationError):
        PostBase(title="", content="some content")


def test_post_base_empty_content_raises():
    from app.schemas.blog import PostBase
    with pytest.raises(ValidationError):
        PostBase(title="Valid Title", content="")


# ---------------------------------------------------------------------------
# BillItem (ngakak)
# ---------------------------------------------------------------------------

def test_bill_item_valid():
    from app.schemas.ngakak import BillItem
    item = BillItem(item="Pizza", price=Decimal("12.99"))
    assert item.item == "Pizza"
    assert item.price == Decimal("12.99")


def test_bill_item_missing_item_raises():
    from app.schemas.ngakak import BillItem
    with pytest.raises(ValidationError):
        BillItem(price=Decimal("5.00"))


def test_bill_item_missing_price_raises():
    from app.schemas.ngakak import BillItem
    with pytest.raises(ValidationError):
        BillItem(item="Pizza")


# ---------------------------------------------------------------------------
# PersonBillDetails (ngakak)
# ---------------------------------------------------------------------------

def test_person_bill_details_valid():
    from app.schemas.ngakak import PersonBillDetails, BillItem
    schema = PersonBillDetails(
        items=[BillItem(item="Burger", price=Decimal("10"))],
        individual_total=Decimal("10"),
        vat_share=Decimal("1"),
        other_share=Decimal("0.5"),
        discount_share=Decimal("0"),
        final_total=Decimal("11.5"),
    )
    assert schema.final_total == Decimal("11.5")
    assert len(schema.items) == 1


def test_person_bill_details_missing_field_raises():
    from app.schemas.ngakak import PersonBillDetails
    with pytest.raises(ValidationError):
        PersonBillDetails(
            items=[],
            individual_total=Decimal("10"),
            vat_share=Decimal("1"),
            # missing other_share, discount_share, final_total
        )


# ---------------------------------------------------------------------------
# TokenCount (ngakak)
# ---------------------------------------------------------------------------

def test_token_count_valid():
    from app.schemas.ngakak import TokenCount
    schema = TokenCount(image=1000, analysis=500)
    assert schema.image == 1000
    assert schema.analysis == 500


# ---------------------------------------------------------------------------
# BillAnalysisResponse (ngakak)
# ---------------------------------------------------------------------------

def test_bill_analysis_response_valid():
    from app.schemas.ngakak import BillAnalysisResponse, PersonBillDetails, BillItem, TokenCount
    schema = BillAnalysisResponse(
        split_details={
            "Alice": PersonBillDetails(
                items=[BillItem(item="Salad", price=Decimal("8"))],
                individual_total=Decimal("8"),
                vat_share=Decimal("1"),
                other_share=Decimal("0"),
                discount_share=Decimal("0"),
                final_total=Decimal("9"),
            )
        },
        total_bill=Decimal("9"),
        subtotal=Decimal("8"),
        subtotal_vat=Decimal("1"),
        subtotal_other=Decimal("0"),
        subtotal_discount=Decimal("0"),
        currency="USD",
        image_description="Restaurant receipt",
        token_count=TokenCount(image=800, analysis=400),
    )
    assert schema.currency == "USD"
    assert "Alice" in schema.split_details
    assert schema.total_bill == Decimal("9")


def test_bill_analysis_response_missing_currency_raises():
    from app.schemas.ngakak import BillAnalysisResponse
    with pytest.raises(ValidationError):
        BillAnalysisResponse(
            split_details={},
            total_bill=Decimal("0"),
            subtotal=Decimal("0"),
            subtotal_vat=Decimal("0"),
            subtotal_other=Decimal("0"),
            subtotal_discount=Decimal("0"),
            # missing currency, image_description, token_count
        )
