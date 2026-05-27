"""MCP client for connecting to remote MCP servers via streamable HTTP."""
import json
from contextlib import asynccontextmanager, AsyncExitStack
from typing import Any, AsyncGenerator

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@asynccontextmanager
async def connect_mcp(endpoint: str) -> AsyncGenerator["MCPSession", None]:
    """Connect to remote MCP server. Use as async context manager."""
    async with AsyncExitStack() as stack:
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamablehttp_client(endpoint)
        )
        session = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        yield MCPSession(session)


class MCPSession:
    """Wraps an MCP ClientSession for tool listing and execution."""

    def __init__(self, session: ClientSession):
        self._session = session

    async def list_tools(self) -> list[dict]:
        """List tools in Anthropic format."""
        result = await self._session.list_tools()
        tools = []
        for tool in result.tools:
            schema = tool.inputSchema or {"type": "object", "properties": {}}
            tools.append({
                "name": tool.name,
                "description": tool.description or f"Tool: {tool.name}",
                "input_schema": schema,
            })
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool. Returns JSON string."""
        result = await self._session.call_tool(name, arguments)
        parts = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        return "".join(parts)
