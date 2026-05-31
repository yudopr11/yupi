"""MCP client with connection pooling for remote MCP servers."""
import asyncio
import ipaddress
import logging
import socket
from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import urlparse

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
]


def _is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is in any blocked network."""
    # Canonicalize IPv4-mapped IPv6 to IPv4 for proper matching
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in network for network in _BLOCKED_NETWORKS)


def validate_mcp_endpoint(url: str) -> str:
    """Validate MCP endpoint URL is not targeting internal/private networks.

    Returns the resolved IP address string for TOCTOU-safe connection.
    Raises ValueError if the URL targets a blocked network.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a hostname")

    if hostname.lower() in ("localhost", "0.0.0.0", "::"):
        raise ValueError("Cannot connect to localhost")

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    resolved_ips = []
    for family, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_ip_blocked(ip):
            raise ValueError(f"Cannot connect to private/internal IP: {ip}")
        resolved_ips.append(str(ip))

    if not resolved_ips:
        raise ValueError(f"No addresses resolved for {hostname}")

    return resolved_ips[0]  # Return first resolved IP for direct connection

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
    """Holds a single MCP connection with auto-reconnect."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.session: MCPSession | None = None
        self.tools: list[dict] = []
        self.tool_sessions: dict[str, MCPSession] = {}
        self._stack: AsyncExitStack | None = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> bool:
        """Create new connection. Must hold _lock."""
        stack = AsyncExitStack()
        try:
            # Resolve DNS once, validate, then connect with resolved IP to prevent DNS rebinding
            resolved_ip = validate_mcp_endpoint(self.endpoint)
            parsed = urlparse(self.endpoint)
            # Build IP-based URL, preserving port and path
            ip_url = f"{parsed.scheme}://{resolved_ip}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{parsed.path or ''}"
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamablehttp_client(ip_url)
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
            await stack.aclose()
            self.session = None
            return False

    async def _reconnect(self) -> bool:
        """Close existing connection and create new one. Must hold _lock."""
        await self._close_internal()
        return await self._connect()

    async def _close_internal(self):
        """Close without acquiring lock."""
        if self._stack:
            try:
                await self._stack.aclose()
            except Exception:
                logger.debug("Error closing MCP connection", exc_info=True)
            self._stack = None
        self.session = None
        self.tools = []
        self.tool_sessions = {}

    async def ensure_connected(self) -> bool:
        """Connect if not already connected. Returns True if successful."""
        if self.session is not None:
            return True
        async with self._lock:
            if self.session is not None:
                return True
            return await self._connect()

    async def call_tool_with_retry(self, name: str, arguments: dict[str, Any], retries: int = 2) -> str:
        """Call tool with automatic reconnect on failure."""
        for attempt in range(retries + 1):
            if not await self.ensure_connected():
                raise RuntimeError(f"MCP connection failed for {self.endpoint}")
            session = self.session
            if session is None:
                continue
            try:
                return await session.call_tool(name, arguments)
            except Exception as e:
                if attempt < retries:
                    logger.info("MCP tool call failed, reconnecting: %s", e)
                    async with self._lock:
                        await self._reconnect()
                else:
                    raise

    async def close(self):
        """Close the connection."""
        async with self._lock:
            await self._close_internal()


class MCPPool:
    """Manages pooled MCP connections per user."""

    def __init__(self):
        # user_id -> {endpoint -> _PooledConnection}
        self._pool: dict[str, dict[str, _PooledConnection]] = {}
        self._lock = asyncio.Lock()

    async def get_sessions(
        self, user_id: str, endpoints: list[str]
    ) -> tuple[dict[str, _PooledConnection], list[dict]] | None:
        """Get or create MCP sessions for a user's endpoints.

        Returns (conn_map, remote_tools) or None if no connections succeeded.
        conn_map maps tool_name -> _PooledConnection (for retry on call).
        """
        if not endpoints:
            return None

        async with self._lock:
            user_conns = self._pool.setdefault(user_id, {})

            # Remove endpoints no longer in user's config
            to_remove = [ep for ep in user_conns if ep not in endpoints]
            for ep in to_remove:
                await user_conns.pop(ep)._close_internal()

        # Connect to any new endpoints
        for ep in endpoints:
            async with self._lock:
                conn = self._pool[user_id].get(ep)
                if conn is None:
                    conn = _PooledConnection(ep)
                    self._pool[user_id][ep] = conn
            await conn.ensure_connected()

        # Collect all tools and connections
        conn_map: dict[str, _PooledConnection] = {}
        remote_tools: list[dict] = []
        async with self._lock:
            for ep in endpoints:
                conn = self._pool[user_id].get(ep)
                if conn and conn.session:
                    for tool_name in conn.tool_sessions:
                        conn_map[tool_name] = conn
                    remote_tools.extend(conn.tools)

        if not conn_map:
            return None
        return conn_map, remote_tools

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
