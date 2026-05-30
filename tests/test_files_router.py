"""Tests for app/routers/files.py endpoints."""
from unittest.mock import MagicMock, patch
import uuid
import pytest


def test_files_router_exists():
    from app.routers.files import router
    assert router.prefix == "/files"
    assert "Files" in router.tags


def test_file_upload_model_exists():
    from app.models.file import FileUpload
    assert FileUpload.__tablename__ == "file_uploads"


def test_file_upload_model_fields():
    from app.models.file import FileUpload
    columns = {c.name for c in FileUpload.__table__.columns}
    assert "id" in columns
    assert "user_id" in columns
    assert "filename" in columns
    assert "original_filename" in columns
    assert "content_type" in columns
    assert "size_bytes" in columns
    assert "storage_key" in columns
    assert "bucket" in columns
    assert "is_orphan" in columns
    assert "deleted_at" in columns
    assert "created_at" in columns
    assert "updated_at" in columns


def test_file_upload_model_indexes():
    from app.models.file import FileUpload
    index_names = {idx.name for idx in FileUpload.__table__.indexes}
    assert "ix_file_uploads_user_id" in index_names
    assert "ix_file_uploads_is_orphan" in index_names
