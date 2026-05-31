"""Tests for ngakak rate limiting and IP utilities."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytest


@pytest.fixture(autouse=True)
def clear_ngakak_request_counts():
    from app.routers import ngakak as ngakak_module
    ngakak_module.request_counts.clear()
    ngakak_module.last_cleanup = datetime.now() - timedelta(days=1)
    yield
    ngakak_module.request_counts.clear()


def test_get_real_ip_from_forwarded_header():
    """Should extract IP from X-Forwarded-For header when trusted."""
    from unittest.mock import patch
    from app.routers.ngakak import _get_real_ip

    request = MagicMock()
    request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
    request.client.host = "10.0.0.1"

    with patch("app.routers.ngakak.settings") as mock_settings:
        mock_settings.NGAKAK_TRUST_X_FORWARDED_FOR = True
        assert _get_real_ip(request) == "1.2.3.4"


def test_get_real_ip_from_client_host():
    """Should fall back to request.client.host when no forwarded header."""
    from app.routers.ngakak import _get_real_ip

    request = MagicMock()
    request.headers = {}
    request.client.host = "10.0.0.1"

    assert _get_real_ip(request) == "10.0.0.1"


def test_get_real_ip_strips_whitespace():
    """Should strip whitespace from forwarded IP when trusted."""
    from unittest.mock import patch
    from app.routers.ngakak import _get_real_ip

    request = MagicMock()
    request.headers = {"X-Forwarded-For": "  1.2.3.4  , 5.6.7.8"}
    request.client.host = "10.0.0.1"

    with patch("app.routers.ngakak.settings") as mock_settings:
        mock_settings.NGAKAK_TRUST_X_FORWARDED_FOR = True
        assert _get_real_ip(request) == "1.2.3.4"


def test_cleanup_old_records_removes_stale():
    """cleanup_old_records should remove entries older than 1 day."""
    from app.routers.ngakak import request_counts, cleanup_old_records, last_cleanup
    import app.routers.ngakak as ngakak

    # Set up old data
    yesterday = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    request_counts["1.2.3.4"][yesterday] = 5
    request_counts["1.2.3.4"][today] = 1
    request_counts["5.6.7.8"][yesterday] = 3

    # Force cleanup by setting last_cleanup to the past
    ngakak.last_cleanup = datetime.now() - timedelta(hours=2)
    cleanup_old_records()

    # Old dates should be removed
    assert yesterday not in request_counts.get("1.2.3.4", {})
    # Today's data should remain
    assert request_counts["1.2.3.4"][today] == 1
    # IP with no remaining dates should be removed
    assert "5.6.7.8" not in request_counts


def test_cleanup_respects_interval():
    """cleanup_old_records should skip if called within CLEANUP_INTERVAL."""
    from app.routers.ngakak import request_counts, cleanup_old_records
    import app.routers.ngakak as ngakak

    request_counts["test"]["2020-01-01"] = 999
    ngakak.last_cleanup = datetime.now()  # Just cleaned

    cleanup_old_records()

    # Should NOT have cleaned up because interval hasn't passed
    assert "2020-01-01" in request_counts["test"]
