"""MCP client with connection pooling for remote MCP servers."""
import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

# Suppress noisy transport-level reconnect logs
logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)


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


class _PooledConnection:
    """Holds a single MCP connection with its exit stack."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.session: MCPSession | None = None
        self.tools: list[dict] = []
        self.tool_sessions: dict[str, MCPSession] = {}
        self._stack: AsyncExitStack | None = None
        self._lock = asyncio.Lock()

    async def ensure_connected(self) -> bool:
        """Connect if not already connected. Returns True if successful."""
        if self.session is not None:
            return True
        async with self._lock:
            # Double-check after acquiring lock
            if self.session is not None:
                return True
            try:
                stack = AsyncExitStack()
                read_stream, write_stream, _ = await stack.enter_async_context(
                    streamablehttp_client(self.endpoint)
                )
                client = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await client.initialize()
                self._stack = stack
                self.session = MCPSession(client)
                self.tools = await self.session.list_tools()
                self.tool_sessions = {t["name"]: self.session for t in self.tools}
                return True
            except Exception as e:
                logger.warning("MCP connect failed for %s: %s", self.endpoint, e)
                return False

    async def close(self):
        """Close the connection."""
        if self._stack:
            try:
                await self._stack.aclose()
            except Exception:
                pass
            self._stack = None
        self.session = None
        self.tools = []
        self.tool_sessions = {}


class MCPPool:
    """Manages pooled MCP connections per user."""

    def __init__(self):
        # user_id -> {endpoint -> _PooledConnection}
        self._pool: dict[str, dict[str, _PooledConnection]] = {}
        self._lock = asyncio.Lock()

    async def get_sessions(
        self, user_id: str, endpoints: list[str]
    ) -> tuple[dict[str, MCPSession], list[dict]] | None:
        """Get or create MCP sessions for a user's endpoints.

        Returns (tool_sessions, remote_tools) or None if no connections succeeded.
        """
        if not endpoints:
            return None

        async with self._lock:
            user_conns = self._pool.setdefault(user_id, {})

            # Remove endpoints no longer in user's config
            to_remove = [ep for ep in user_conns if ep not in endpoints]
            for ep in to_remove:
                await user_conns.pop(ep).close()

        # Connect to any new endpoints (outside global lock)
        for ep in endpoints:
            async with self._lock:
                conn = self._pool[user_id].get(ep)
            if conn is None:
                conn = _PooledConnection(ep)
                async with self._lock:
                    self._pool[user_id][ep] = conn
            await conn.ensure_connected()

        # Collect all tools and sessions
        tool_sessions: dict[str, MCPSession] = {}
        remote_tools: list[dict] = []
        async with self._lock:
            for ep in endpoints:
                conn = self._pool[user_id].get(ep)
                if conn and conn.session:
                    tool_sessions.update(conn.tool_sessions)
                    remote_tools.extend(conn.tools)

        if not tool_sessions:
            return None
        return tool_sessions, remote_tools

    async def invalidate(self, user_id: str):
        """Close and remove all connections for a user."""
        async with self._lock:
            conns = self._pool.pop(user_id, {})
        for conn in conns.values():
            await conn.close()

    async def close_all(self):
        """Shutdown: close all connections."""
        async with self._lock:
            all_conns = list(self._pool.values())
            self._pool.clear()
        for user_conns in all_conns:
            for conn in user_conns.values():
                await conn.close()


# Global singleton
mcp_pool = MCPPool()
