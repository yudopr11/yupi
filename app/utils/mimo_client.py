import anthropic
from typing import AsyncGenerator


class MiMoClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[dict, None]:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                yield event

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> anthropic.types.Message:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        return await self.client.messages.create(**kwargs)
