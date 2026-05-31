"""Tests for superuser creation utility."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


async def test_create_superuser_creates_when_none_exist():
    """Should create a superuser when no superuser exists in DB."""
    from app.utils.superuser import create_superuser

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("app.utils.superuser.settings") as mock_settings, \
         patch("app.utils.superuser.get_password_hash", new_callable=AsyncMock) as mock_hash:
        mock_settings.SUPERUSER_USERNAME = "admin"
        mock_settings.SUPERUSER_EMAIL = "admin@test.com"
        mock_settings.SUPERUSER_PASSWORD = "securepass123"
        mock_hash.return_value = "hashed_pw"

        await create_superuser(mock_db)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    # Verify the user object passed to add
    added_user = mock_db.add.call_args[0][0]
    assert added_user.username == "admin"
    assert added_user.email == "admin@test.com"
    assert added_user.is_superuser is True


async def test_create_superuser_skips_when_superuser_exists():
    """Should not create a superuser when one already exists."""
    from app.utils.superuser import create_superuser

    mock_db = MagicMock()
    existing_user = MagicMock()
    existing_user.is_superuser = True
    mock_db.query.return_value.filter.return_value.first.return_value = existing_user

    await create_superuser(mock_db)

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


async def test_create_superuser_hashes_password():
    """Should hash the password before storing."""
    from app.utils.superuser import create_superuser

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("app.utils.superuser.settings") as mock_settings, \
         patch("app.utils.superuser.get_password_hash", new_callable=AsyncMock) as mock_hash:
        mock_settings.SUPERUSER_USERNAME = "admin"
        mock_settings.SUPERUSER_EMAIL = "admin@test.com"
        mock_settings.SUPERUSER_PASSWORD = "mypassword"
        mock_hash.return_value = "hashed_mypassword"

        await create_superuser(mock_db)

    mock_hash.assert_called_once_with("mypassword")
    added_user = mock_db.add.call_args[0][0]
    assert added_user.password == "hashed_mypassword"
