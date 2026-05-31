"""Tests for auth rate limiting and BoundedDict."""
import time as _time
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture(autouse=True)
def clear_rate_limit_state():
    from app.routers.auth import _login_attempts
    _login_attempts.clear()
    yield
    _login_attempts.clear()


def test_check_rate_limit_allows_under_limit():
    """First 5 attempts should not be rate limited."""
    from app.routers.auth import _check_rate_limit, _login_attempts

    for i in range(5):
        assert _check_rate_limit("testuser", max_attempts=5, window=300) is False


def test_check_rate_limit_blocks_at_limit():
    """6th attempt should be rate limited."""
    from app.routers.auth import _check_rate_limit, _login_attempts

    for i in range(5):
        _check_rate_limit("testuser2", max_attempts=5, window=300)
    assert _check_rate_limit("testuser2", max_attempts=5, window=300) is True


def test_check_rate_limit_different_keys_independent():
    """Rate limits are per-key — different users are independent."""
    from app.routers.auth import _check_rate_limit, _login_attempts

    for i in range(5):
        _check_rate_limit("user_a", max_attempts=5, window=300)
    # user_a is now limited
    assert _check_rate_limit("user_a", max_attempts=5, window=300) is True
    # user_b is not
    assert _check_rate_limit("user_b", max_attempts=5, window=300) is False


def test_check_rate_limit_window_expiry():
    """Attempts outside the window should be ignored."""
    from app.routers.auth import _check_rate_limit, _login_attempts

    # Record 4 attempts in the past
    now = _time.time()
    _login_attempts["testuser3"] = [now - 400, now - 350, now - 320, now - 310]
    # 5th attempt now — should pass because old ones expired
    assert _check_rate_limit("testuser3", max_attempts=5, window=300) is False


def test_bounded_dict_eviction():
    """BoundedDict should evict oldest entries when maxsize is exceeded."""
    from app.routers.auth import _BoundedDict

    d = _BoundedDict(maxsize=3)
    d["a"] = 1
    d["b"] = 2
    d["c"] = 3
    d["d"] = 4  # should evict "a"

    assert "a" not in d
    assert "d" in d
    assert len(d) == 3


def test_bounded_dict_move_to_end_on_update():
    """Updating an existing key should move it to end (most recent)."""
    from app.routers.auth import _BoundedDict

    d = _BoundedDict(maxsize=3)
    d["a"] = 1
    d["b"] = 2
    d["c"] = 3
    d["a"] = 10  # move "a" to end
    d["d"] = 4   # should evict "b" (oldest)

    assert "b" not in d
    assert "a" in d
    assert d["a"] == 10
