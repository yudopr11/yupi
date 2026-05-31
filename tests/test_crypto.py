"""TDD tests for crypto utility functions."""
import json
import pytest
from app.utils.crypto import (
    encrypt_value,
    decrypt_value,
    mask_value,
    encrypt_endpoint,
    decrypt_endpoint,
)


# ---------------------------------------------------------------------------
# encrypt_value / decrypt_value
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    plain = "my-secret-api-key-12345"
    token = encrypt_value(plain)
    assert token != plain
    assert decrypt_value(token) == plain


def test_encrypt_different_ciphertext_each_time():
    """Fernet uses random IV, so same plaintext produces different ciphertext."""
    plain = "same-input"
    t1 = encrypt_value(plain)
    t2 = encrypt_value(plain)
    assert t1 != t2
    assert decrypt_value(t1) == decrypt_value(t2) == plain


def test_decrypt_invalid_token_raises():
    with pytest.raises(Exception):
        decrypt_value("not-a-valid-fernet-token")


def test_encrypt_empty_string():
    token = encrypt_value("")
    assert decrypt_value(token) == ""


# ---------------------------------------------------------------------------
# mask_value
# ---------------------------------------------------------------------------

def test_mask_value_long_string():
    result = mask_value("abcdefghijklmnop")
    assert result == "abcdef...klmnop"


def test_mask_value_short_string():
    """Short values (<=12 chars) are fully masked."""
    result = mask_value("short")
    assert result == "*****"


def test_mask_value_exact_threshold():
    """12 chars = 6*2, fully masked."""
    result = mask_value("a" * 12)
    assert result == "*" * 12


def test_mask_value_none():
    assert mask_value(None) is None


def test_mask_value_empty():
    assert mask_value("") is None


def test_mask_value_custom_show_chars():
    result = mask_value("abcdefghij", show_chars=2)
    assert result == "ab...ij"


# ---------------------------------------------------------------------------
# encrypt_endpoint / decrypt_endpoint
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_endpoint_roundtrip():
    token = encrypt_endpoint("My MCP", "http://localhost:8000/mcp/abc")
    data = decrypt_endpoint(token)
    assert data["name"] == "My MCP"
    assert data["url"] == "http://localhost:8000/mcp/abc"


def test_decrypt_endpoint_legacy_plaintext_rejected():
    """Legacy plaintext URLs are no longer accepted — returns None."""
    data = decrypt_endpoint("http://old-endpoint.com/mcp")
    assert data is None


def test_decrypt_endpoint_invalid_json_rejected():
    """Invalid JSON is rejected — returns None."""
    data = decrypt_endpoint("not-json-at-all")
    assert data is None


def test_decrypt_endpoint_json_without_url_key():
    """Valid JSON but without 'url' key should return None."""
    # Encrypt a JSON object that lacks the "url" key
    token = encrypt_value(json.dumps({"name": "test", "other": "data"}))
    data = decrypt_endpoint(token)
    assert data is None
