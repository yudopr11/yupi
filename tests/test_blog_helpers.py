"""Tests for app/utils/blog_helpers.py."""
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# generate_slug
# ---------------------------------------------------------------------------

def test_generate_slug_basic():
    from app.utils.blog_helpers import generate_slug
    assert generate_slug("Hello World") == "hello-world"


def test_generate_slug_special_chars():
    from app.utils.blog_helpers import generate_slug
    assert generate_slug("Python 3.12: New Features!") == "python-3-12-new-features"


def test_generate_slug_multiple_spaces():
    from app.utils.blog_helpers import generate_slug
    slug = generate_slug("  FastAPI  Tutorial  ")
    assert " " not in slug
    assert slug == "fastapi-tutorial"


def test_generate_slug_unicode():
    from app.utils.blog_helpers import generate_slug
    slug = generate_slug("Belajar Pemrograman")
    assert slug == "belajar-pemrograman"


# ---------------------------------------------------------------------------
# calculate_reading_time
# ---------------------------------------------------------------------------

def test_calculate_reading_time_short_content():
    from app.utils.blog_helpers import calculate_reading_time
    # Under 300 words → 1 minute minimum
    assert calculate_reading_time("short") == 1


def test_calculate_reading_time_exactly_300_words():
    from app.utils.blog_helpers import calculate_reading_time
    content = " ".join(["word"] * 300)
    assert calculate_reading_time(content) == 1


def test_calculate_reading_time_600_words():
    from app.utils.blog_helpers import calculate_reading_time
    content = " ".join(["word"] * 600)
    assert calculate_reading_time(content) == 2


def test_calculate_reading_time_empty():
    from app.utils.blog_helpers import calculate_reading_time
    assert calculate_reading_time("") == 1


# ---------------------------------------------------------------------------
# truncate_content_for_prompt
# ---------------------------------------------------------------------------

def test_truncate_short_content_unchanged():
    from app.utils.blog_helpers import truncate_content_for_prompt
    content = "short content"
    assert truncate_content_for_prompt(content, max_chars=100) == content


def test_truncate_long_content_has_ellipsis():
    from app.utils.blog_helpers import truncate_content_for_prompt
    content = "A" * 5000
    result = truncate_content_for_prompt(content, max_chars=100)
    assert "..." in result
    assert len(result) <= 110  # some slack for the ellipsis and newlines


def test_truncate_preserves_start_and_end():
    from app.utils.blog_helpers import truncate_content_for_prompt
    start = "START" + "x" * 500
    end = "y" * 500 + "END"
    content = start + end
    result = truncate_content_for_prompt(content, max_chars=20)
    assert "START" in result
    assert "END" in result


# ---------------------------------------------------------------------------
# extract_excerpt_from_text
# ---------------------------------------------------------------------------

def test_extract_excerpt_finds_excerpt_label():
    from app.utils.blog_helpers import extract_excerpt_from_text
    text = "Some text\nexcerpt:\nThis is the excerpt text"
    result = extract_excerpt_from_text(text)
    assert "excerpt" in result.lower() or "this is the excerpt" in result.lower()


def test_extract_excerpt_no_indicator_returns_empty():
    from app.utils.blog_helpers import extract_excerpt_from_text
    result = extract_excerpt_from_text("random text with nothing useful")
    assert result == ""


# ---------------------------------------------------------------------------
# extract_tags_from_text
# ---------------------------------------------------------------------------

def test_extract_tags_from_brackets():
    from app.utils.blog_helpers import extract_tags_from_text
    text = 'Here are the tags: ["Python", "FastAPI", "Testing"]'
    result = extract_tags_from_text(text)
    assert len(result) > 0
    assert any("Python" in tag or "python" in tag.lower() for tag in result)


def test_extract_tags_no_brackets_returns_empty():
    from app.utils.blog_helpers import extract_tags_from_text
    result = extract_tags_from_text("no brackets here just plain text")
    assert result == []


def test_extract_tags_limits_to_five():
    from app.utils.blog_helpers import extract_tags_from_text
    text = '["a", "b", "c", "d", "e", "f", "g"]'
    result = extract_tags_from_text(text)
    assert len(result) <= 5


# ---------------------------------------------------------------------------
# fallback_excerpt
# ---------------------------------------------------------------------------

def test_fallback_excerpt_uses_first_sentence():
    from app.utils.blog_helpers import fallback_excerpt
    content = "This is the first sentence. This is the second sentence."
    result = fallback_excerpt(content)
    assert result == "This is the first sentence"


def test_fallback_excerpt_truncates_long_first_sentence():
    from app.utils.blog_helpers import fallback_excerpt
    content = "A" * 200 + ". Second sentence."
    result = fallback_excerpt(content)
    assert len(result) <= 150
    assert result.endswith("...")


def test_fallback_excerpt_empty_content():
    from app.utils.blog_helpers import fallback_excerpt
    result = fallback_excerpt("")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# generate_post_content (mocked OpenAI)
# ---------------------------------------------------------------------------

def test_generate_post_content_returns_excerpt_and_tags():
    from app.utils.blog_helpers import generate_post_content
    import app.utils.blog_helpers as _bh
    _bh._openai_client = None

    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"excerpt": "Test excerpt", "tags": ["Python", "Testing"]}'

    with patch("app.utils.blog_helpers.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = mock_response
        result = generate_post_content("Test Title", "Test content body")

    assert result["excerpt"] == "Test excerpt"
    assert "Python" in result["tags"]


def test_generate_post_content_api_failure_returns_fallback():
    from app.utils.blog_helpers import generate_post_content
    import app.utils.blog_helpers as _bh
    _bh._openai_client = None

    with patch("app.utils.blog_helpers.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.side_effect = Exception("API error")
        result = generate_post_content("Title", "Some content here. More content.")

    assert isinstance(result["excerpt"], str)
    assert isinstance(result["tags"], list)


def test_generate_post_content_neither_needed_returns_early():
    from app.utils.blog_helpers import generate_post_content
    result = generate_post_content("T", "C", need_excerpt=False, need_tags=False)
    assert result == {"excerpt": "", "tags": []}


# ---------------------------------------------------------------------------
# generate_embedding (mocked OpenAI)
# ---------------------------------------------------------------------------

def test_generate_embedding_returns_vector():
    from app.utils.blog_helpers import generate_embedding
    import app.utils.blog_helpers as _bh
    _bh._openai_client = None

    mock_response = MagicMock()
    mock_response.data[0].embedding = [0.1] * 1536

    with patch("app.utils.blog_helpers.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.embeddings.create.return_value = mock_response
        result = generate_embedding("hello world")

    assert len(result) == 1536
    assert result[0] == 0.1


def test_generate_embedding_empty_text_returns_zero_vector():
    from app.utils.blog_helpers import generate_embedding
    result = generate_embedding("")
    assert len(result) == 1536
    assert all(v == 0.0 for v in result)


def test_generate_embedding_api_failure_returns_zero_vector():
    from app.utils.blog_helpers import generate_embedding
    import app.utils.blog_helpers as _bh
    _bh._openai_client = None

    with patch("app.utils.blog_helpers.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.embeddings.create.side_effect = Exception("API error")
        result = generate_embedding("some text")

    assert len(result) == 1536
    assert all(v == 0.0 for v in result)


# ---------------------------------------------------------------------------
# generate_post_embedding
# ---------------------------------------------------------------------------

def test_generate_post_embedding_combines_title_and_excerpt():
    from app.utils.blog_helpers import generate_post_embedding

    with patch("app.utils.blog_helpers.generate_embedding") as mock_embed:
        mock_embed.return_value = [0.5] * 1536
        result = generate_post_embedding("My Title", "My Excerpt")

    mock_embed.assert_called_once_with("My Title My Excerpt")
    assert result == [0.5] * 1536


def test_generate_slug_empty_string():
    """generate_slug should handle empty string without crashing."""
    from app.utils.blog_helpers import generate_slug
    result = generate_slug("")
    assert isinstance(result, str)
