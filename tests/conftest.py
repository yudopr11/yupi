"""Shared test fixtures for yupi test suite."""
import pytest
from unittest.mock import MagicMock

from app.utils.uuid import uuid7


def make_mock_user(username="testuser", email="test@example.com", is_superuser=False):
    """Create a mock User object for testing."""
    user = MagicMock()
    user.id = uuid7()
    user.username = username
    user.email = email
    user.is_superuser = is_superuser
    return user
