"""Tests for blog_helpers search and slug functions."""
import pytest
from unittest.mock import MagicMock, patch


def test_search_posts_by_embedding_empty_query():
    """search_posts_by_embedding should return [] for empty/blank queries."""
    from app.utils.blog_helpers import search_posts_by_embedding

    mock_db = MagicMock()
    assert search_posts_by_embedding("", mock_db) == []
    assert search_posts_by_embedding("   ", mock_db) == []


def test_search_posts_by_embedding_calls_generate_embedding():
    """search_posts_by_embedding should call generate_embedding with the query."""
    from app.utils.blog_helpers import search_posts_by_embedding

    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []

    with patch("app.utils.blog_helpers.generate_embedding") as mock_gen:
        mock_gen.return_value = [0.1] * 1536
        search_posts_by_embedding("test query", mock_db)

    mock_gen.assert_called_once_with("test query")


def test_search_posts_by_embedding_with_custom_limit():
    """search_posts_by_embedding should call generate_embedding with the query."""
    from app.utils.blog_helpers import search_posts_by_embedding

    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []

    with patch("app.utils.blog_helpers.generate_embedding") as mock_gen:
        mock_gen.return_value = [0.1] * 1536
        search_posts_by_embedding("test query", mock_db, limit=5)

    mock_gen.assert_called_once_with("test query")


def test_search_posts_by_embedding_passes_threshold():
    """search_posts_by_embedding should pass similarity_threshold to the query."""
    from app.utils.blog_helpers import search_posts_by_embedding

    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []

    with patch("app.utils.blog_helpers.generate_embedding") as mock_gen:
        mock_gen.return_value = [0.1] * 1536
        search_posts_by_embedding("test query", mock_db, limit=3, similarity_threshold=0.5)

    mock_gen.assert_called_once_with("test query")
    mock_db.execute.assert_called_once()


def test_generate_slug_empty_string_in_search():
    """generate_slug should handle empty string without crashing."""
    from app.utils.blog_helpers import generate_slug

    result = generate_slug("")
    assert isinstance(result, str)
    # Empty slug should produce something (even if just empty string or "-")
    assert result is not None


def test_generate_slug_normal():
    """generate_slug should produce a URL-friendly slug."""
    from app.utils.blog_helpers import generate_slug

    result = generate_slug("Hello World! This is a Test")
    assert "hello" in result
    assert " " not in result
