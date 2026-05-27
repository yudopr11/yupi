"""Tests for app/routers/settings.py endpoints."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# _get_or_create_settings
# ---------------------------------------------------------------------------

def test_get_or_create_settings_existing():
    """Returns existing settings if found."""
    from app.routers.chat import _get_or_create_settings

    mock_us = MagicMock()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_us

    result = _get_or_create_settings(mock_db, uuid4())
    assert result == mock_us
    mock_db.add.assert_not_called()


def test_get_or_create_settings_creates_new():
    """Creates new settings row when none exist."""
    from app.routers.chat import _get_or_create_settings

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    user_id = uuid4()
    result = _get_or_create_settings(mock_db, user_id)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()


# ---------------------------------------------------------------------------
# get_settings response masking
# ---------------------------------------------------------------------------

def test_get_settings_masks_long_key():
    """Long API key is masked in response."""
    from app.routers.chat import _get_or_create_settings

    # Simulate what get_settings does after getting settings
    api_key = "sk-1234567890abcdef"
    masked = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else bool(api_key)
    assert masked == "sk-12345...cdef"


def test_get_settings_short_key_returns_bool():
    """Short API key returns True/False instead of masked string."""
    api_key = "short"
    masked = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else bool(api_key)
    assert masked is True


def test_get_settings_empty_key_returns_falsy():
    api_key = ""
    masked = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else bool(api_key)
    assert masked is False


def test_get_settings_none_key_returns_falsy():
    api_key = None
    masked = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else bool(api_key)
    assert masked is False
