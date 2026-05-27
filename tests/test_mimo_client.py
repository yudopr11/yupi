"""Tests for app/services/mimo_client.py."""
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


def test_mimo_client_init():
    """MiMoClient stores model and creates Anthropic client."""
    from app.utils.mimo_client import MiMoClient

    with patch("app.utils.mimo_client.anthropic.AsyncAnthropic") as mock_cls:
        client = MiMoClient(api_key="sk-test", base_url="https://example.com", model="mimo-v2.5")

    assert client.model == "mimo-v2.5"
    mock_cls.assert_called_once_with(api_key="sk-test", base_url="https://example.com")


@pytest.mark.asyncio
async def test_mimo_client_chat():
    """chat() delegates to client.messages.create with correct kwargs."""
    from app.utils.mimo_client import MiMoClient

    mock_message = MagicMock()
    mock_create = AsyncMock(return_value=mock_message)

    with patch("app.utils.mimo_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = mock_create
        client = MiMoClient(api_key="sk-test", base_url="https://x.com", model="m")

        result = await client.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[{"name": "t"}],
            system="Be helpful",
            max_tokens=1024,
        )

    assert result == mock_message
    mock_create.assert_awaited_once_with(
        model="m",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=1024,
        tools=[{"name": "t"}],
        system="Be helpful",
    )


@pytest.mark.asyncio
async def test_mimo_client_chat_no_optional():
    """chat() without tools/system omits them from kwargs."""
    from app.utils.mimo_client import MiMoClient

    mock_create = AsyncMock(return_value=MagicMock())

    with patch("app.utils.mimo_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = mock_create
        client = MiMoClient(api_key="sk", base_url="https://x.com", model="m")
        await client.chat(messages=[{"role": "user", "content": "Hi"}])

    kwargs = mock_create.call_args[1]
    assert "tools" not in kwargs
    assert "system" not in kwargs


@pytest.mark.asyncio
async def test_mimo_client_stream_chat():
    """stream_chat() uses client.messages.stream context manager."""
    from app.utils.mimo_client import MiMoClient

    mock_event = MagicMock()

    class MockAsyncIterator:
        def __init__(self, items):
            self._iter = iter(items)
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=MockAsyncIterator([mock_event]))
    mock_stream.__aexit__ = AsyncMock(return_value=False)

    mock_stream_fn = MagicMock(return_value=mock_stream)

    with patch("app.utils.mimo_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.stream = mock_stream_fn
        client = MiMoClient(api_key="sk", base_url="https://x.com", model="m")

        events = []
        async for event in client.stream_chat(messages=[{"role": "user", "content": "Hi"}]):
            events.append(event)

    assert len(events) == 1
    assert events[0] == mock_event
    mock_stream_fn.assert_called_once()
