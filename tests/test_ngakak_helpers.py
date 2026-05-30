"""Tests for ngakak router helpers: validate_image, cleanup_old_records, rate limiting."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# validate_image
# ---------------------------------------------------------------------------

def _make_upload(content_type: str, size_bytes: int = 100):
    file_obj = MagicMock()
    # Simulate seek/tell for size check
    file_obj.tell.return_value = size_bytes
    upload = MagicMock()
    upload.content_type = content_type
    upload.file = file_obj
    return upload


def test_validate_image_jpeg_ok():
    from app.routers.ngakak import validate_image
    upload = _make_upload("image/jpeg", size_bytes=100)
    validate_image(upload)  # should not raise


def test_validate_image_png_ok():
    from app.routers.ngakak import validate_image
    upload = _make_upload("image/png", size_bytes=500)
    validate_image(upload)


def test_validate_image_webp_ok():
    from app.routers.ngakak import validate_image
    upload = _make_upload("image/webp", size_bytes=200)
    validate_image(upload)


def test_validate_image_pdf_raises_415():
    from app.routers.ngakak import validate_image
    upload = _make_upload("application/pdf", size_bytes=100)
    with pytest.raises(HTTPException) as exc:
        validate_image(upload)
    assert exc.value.status_code == 415


def test_validate_image_text_raises_415():
    from app.routers.ngakak import validate_image
    upload = _make_upload("text/plain")
    with pytest.raises(HTTPException) as exc:
        validate_image(upload)
    assert exc.value.status_code == 415


def test_validate_image_too_large_raises_413():
    from app.routers.ngakak import validate_image
    too_large = 6 * 1024 * 1024  # 6MB
    upload = _make_upload("image/jpeg", size_bytes=too_large)
    with pytest.raises(HTTPException) as exc:
        validate_image(upload)
    assert exc.value.status_code == 413


def test_validate_image_exactly_5mb_ok():
    from app.routers.ngakak import validate_image
    exactly_5mb = 5 * 1024 * 1024
    upload = _make_upload("image/jpeg", size_bytes=exactly_5mb)
    validate_image(upload)  # at limit is allowed


# ---------------------------------------------------------------------------
# cleanup_old_records
# ---------------------------------------------------------------------------

def test_cleanup_removes_old_entries():
    import app.routers.ngakak as ngakak_module

    # Directly populate request_counts with old data
    old_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    ngakak_module.request_counts.clear()
    ngakak_module.request_counts["192.168.1.1"][old_date] = 5
    ngakak_module.request_counts["192.168.1.1"][today] = 1
    # Force last_cleanup to be old enough
    ngakak_module.last_cleanup = datetime.now() - timedelta(hours=2)

    ngakak_module.cleanup_old_records()

    # Old date should be removed, today should remain
    assert old_date not in ngakak_module.request_counts.get("192.168.1.1", {})
    assert ngakak_module.request_counts["192.168.1.1"][today] == 1


def test_cleanup_skips_if_recent():
    import app.routers.ngakak as ngakak_module

    old_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    ngakak_module.request_counts.clear()
    ngakak_module.request_counts["10.0.0.1"][old_date] = 3
    # last_cleanup is very recent → cleanup should NOT run
    ngakak_module.last_cleanup = datetime.now()

    ngakak_module.cleanup_old_records()

    # Old date should still be there (cleanup was skipped)
    assert old_date in ngakak_module.request_counts["10.0.0.1"]


# ---------------------------------------------------------------------------
# Rate limit constants
# ---------------------------------------------------------------------------

def test_guest_rate_limit_is_3():
    from app.routers.ngakak import GUEST_RATE_LIMIT
    assert GUEST_RATE_LIMIT == 3


def test_allowed_image_types_include_common_formats():
    from app.routers.ngakak import ALLOWED_IMAGE_TYPES
    assert "image/jpeg" in ALLOWED_IMAGE_TYPES
    assert "image/png" in ALLOWED_IMAGE_TYPES
    assert "image/webp" in ALLOWED_IMAGE_TYPES
