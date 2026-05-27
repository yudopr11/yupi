"""Encrypt/decrypt sensitive fields using Fernet, derived from SECRET_KEY."""
import json
import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        _fernet = Fernet(base64.urlsafe_b64encode(key))
    return _fernet


def encrypt_value(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()


def mask_value(value: str | None, show_chars: int = 6) -> str | None:
    """Return masked version: show first and last N chars."""
    if not value:
        return None
    if len(value) <= show_chars * 2:
        return "*" * len(value)
    return f"{value[:show_chars]}...{value[-show_chars:]}"


def encrypt_endpoint(name: str, url: str) -> str:
    """Encrypt endpoint name+url as JSON string."""
    return encrypt_value(json.dumps({"name": name, "url": url}))


def decrypt_endpoint(token: str) -> dict:
    """Decrypt endpoint, returns {name, url}. Falls back to legacy format."""
    try:
        data = json.loads(decrypt_value(token))
        if isinstance(data, dict) and "url" in data:
            return {"name": data.get("name", ""), "url": data["url"]}
    except (json.JSONDecodeError, Exception):
        pass
    # Legacy: token is a plaintext URL string
    return {"name": "", "url": token}
