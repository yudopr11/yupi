"""Tests for app/utils/file_service.py and app/routers/files.py."""
from unittest.mock import MagicMock, patch, PropertyMock
import uuid
import pytest

from app.utils.file_service import validate_file, ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------

class FakeUploadFile:
    def __init__(self, content_type: str, filename: str = "test.jpg"):
        self.content_type = content_type
        self.filename = filename


def test_validate_file_jpeg_ok():
    validate_file(FakeUploadFile("image/jpeg"))


def test_validate_file_png_ok():
    validate_file(FakeUploadFile("image/png"))


def test_validate_file_webp_ok():
    validate_file(FakeUploadFile("image/webp"))


def test_validate_file_pdf_ok():
    validate_file(FakeUploadFile("application/pdf"))


def test_validate_file_text_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        validate_file(FakeUploadFile("text/plain"))
    assert exc_info.value.status_code == 415


def test_validate_file_svg_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        validate_file(FakeUploadFile("image/svg+xml"))
    assert exc_info.value.status_code == 415


def test_allowed_types_include_common_formats():
    assert "image/jpeg" in ALLOWED_IMAGE_TYPES
    assert "image/png" in ALLOWED_IMAGE_TYPES
    assert "image/webp" in ALLOWED_IMAGE_TYPES
    assert "application/pdf" in ALLOWED_IMAGE_TYPES


def test_max_file_size_is_10mb():
    assert MAX_FILE_SIZE == 10 * 1024 * 1024
