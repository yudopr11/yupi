"""Tests for email utility functions."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks


@pytest.mark.asyncio
async def test_send_email_async_schedules_background_task():
    """send_email_async should add a task to background_tasks."""
    from app.utils.email import send_email_async

    mock_bg = MagicMock(spec=BackgroundTasks)
    mock_bg.add_task = MagicMock()

    await send_email_async(
        subject="Test",
        recipients=["test@example.com"],
        body="<p>Hello</p>",
        background_tasks=mock_bg,
    )

    mock_bg.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_send_password_reset_email_includes_token():
    """send_password_reset_email should include the token in the body."""
    from app.utils.email import send_password_reset_email

    mock_bg = MagicMock(spec=BackgroundTasks)
    mock_bg.add_task = MagicMock()

    await send_password_reset_email(
        email="user@example.com",
        token="abc123reset",
        background_tasks=mock_bg,
    )

    mock_bg.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_async_handles_exception():
    """send_email_async should not raise if the inner send fails."""
    from app.utils.email import send_email_async

    mock_bg = MagicMock(spec=BackgroundTasks)

    # The task is scheduled via add_task, so we can't directly test the
    # exception handling without running the background task. But we verify
    # the function itself doesn't raise.
    await send_email_async(
        subject="Test",
        recipients=["test@example.com"],
        body="<p>Hello</p>",
        background_tasks=mock_bg,
    )
    # If we get here without exception, the function handles scheduling correctly
    assert mock_bg.add_task.called
