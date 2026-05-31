"""Tests for ngakak router helpers: validate_image, cleanup_old_records, rate limiting."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def clear_ngakak_request_counts():
    import app.routers.ngakak as ngakak_module
    ngakak_module.request_counts.clear()
    ngakak_module.last_cleanup = datetime.now() - timedelta(days=1)
    yield
    ngakak_module.request_counts.clear()


# ---------------------------------------------------------------------------
# validate_image
# ---------------------------------------------------------------------------

MAGIC_JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 8
MAGIC_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 4
MAGIC_WEBP = b'RIFF\x00\x00\x00\x00WEBP'
MAGIC_GIF = b'GIF89a' + b'\x00' * 6
MAGIC_FAKE = b'\x00\x00\x00\x00' + b'\x00' * 8


def _make_upload(content_type: str, size_bytes: int = 100, magic: bytes = MAGIC_FAKE):
    from io import BytesIO
    file_obj = BytesIO(magic)
    # Simulate seek/tell for size check
    file_obj.tell = lambda: size_bytes
    upload = MagicMock()
    upload.content_type = content_type
    upload.file = file_obj
    return upload


def test_validate_image_jpeg_ok():
    from app.routers.ngakak import validate_image
    upload = _make_upload("image/jpeg", size_bytes=100, magic=MAGIC_JPEG)
    validate_image(upload)  # should not raise


def test_validate_image_png_ok():
    from app.routers.ngakak import validate_image
    upload = _make_upload("image/png", size_bytes=500, magic=MAGIC_PNG)
    validate_image(upload)


def test_validate_image_webp_ok():
    from app.routers.ngakak import validate_image
    upload = _make_upload("image/webp", size_bytes=200, magic=MAGIC_WEBP)
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
    upload = _make_upload("image/jpeg", size_bytes=too_large, magic=MAGIC_JPEG)
    with pytest.raises(HTTPException) as exc:
        validate_image(upload)
    assert exc.value.status_code == 413


def test_validate_image_exactly_5mb_ok():
    from app.routers.ngakak import validate_image
    exactly_5mb = 5 * 1024 * 1024
    upload = _make_upload("image/jpeg", size_bytes=exactly_5mb, magic=MAGIC_JPEG)
    validate_image(upload)  # at limit is allowed


def test_validate_image_mismatched_but_valid_magic_accepted():
    """Content_type says JPEG but file has PNG magic — still accepted (valid image)."""
    from app.routers.ngakak import validate_image
    # The validation checks if magic bytes are ANY valid image format,
    # not if they match the content_type. This is defense-in-depth.
    upload = _make_upload("image/jpeg", size_bytes=100, magic=MAGIC_PNG)
    validate_image(upload)  # should NOT raise — PNG is a valid image format


def test_validate_image_non_image_magic_rejected():
    """Image content_type with non-image magic bytes should be rejected."""
    from app.routers.ngakak import validate_image
    # Content type says JPEG but magic bytes are garbage
    upload = _make_upload("image/jpeg", size_bytes=100, magic=MAGIC_FAKE)
    with pytest.raises(HTTPException) as exc:
        validate_image(upload)
    assert exc.value.status_code == 415


def test_validate_image_gif_rejected():
    """image/gif is not in ALLOWED_IMAGE_TYPES, so it should be rejected."""
    from app.routers.ngakak import validate_image
    upload = _make_upload("image/gif", size_bytes=100, magic=MAGIC_GIF)
    with pytest.raises(HTTPException) as exc:
        validate_image(upload)
    assert exc.value.status_code == 415


# ---------------------------------------------------------------------------
# cleanup_old_records
# ---------------------------------------------------------------------------

def test_cleanup_removes_old_entries():
    import app.routers.ngakak as ngakak_module

    # Directly populate request_counts with old data
    old_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

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
