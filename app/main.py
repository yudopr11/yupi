import asyncio
import logging
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.mcp.server import create_mcp_asgi_app, mcp
from app.middleware.cors import init_cors
from app.routers import auth, blog, cuan, ngakak, chat, files
from app.utils.database import get_db
from app.utils.mcp_client import mcp_pool
from app.utils.superuser import create_superuser

# FastMCP Starlette app — has its own lifespan (session manager task group)
_mcp_starlette = mcp.streamable_http_app()
# Auth wrapper — no lifespan, wraps _mcp_starlette for HTTP requests
_mcp_auth = create_mcp_asgi_app(_mcp_starlette)


async def _dual_lifespan(fastapi_app: ASGIApp, mcp_app: ASGIApp, scope: Scope, receive: Receive, send: Send) -> None:
    """Forward lifespan events to both FastAPI and FastMCP concurrently."""
    startup = await receive()

    fastapi_q: asyncio.Queue = asyncio.Queue()
    mcp_q: asyncio.Queue = asyncio.Queue()
    await fastapi_q.put(startup)
    await mcp_q.put(startup)

    fastapi_ready = asyncio.Event()
    mcp_ready = asyncio.Event()
    fastapi_done = asyncio.Event()
    mcp_done = asyncio.Event()

    async def fastapi_send(msg: dict) -> None:
        if msg["type"] == "lifespan.startup.complete":
            fastapi_ready.set()
        elif msg["type"] == "lifespan.startup.failed":
            err = msg.get("message", "unknown error")
            logger.error("FastAPI startup failed: %s", err)
            fastapi_ready.set()
            raise RuntimeError(f"FastAPI startup failed: {err}")
        elif msg["type"] == "lifespan.shutdown.complete":
            fastapi_done.set()

    async def mcp_send(msg: dict) -> None:
        if msg["type"] == "lifespan.startup.complete":
            mcp_ready.set()
        elif msg["type"] == "lifespan.startup.failed":
            err = msg.get("message", "unknown error")
            logger.error("FastMCP startup failed: %s", err)
            mcp_ready.set()
            raise RuntimeError(f"FastMCP startup failed: {err}")
        elif msg["type"] == "lifespan.shutdown.complete":
            mcp_done.set()

    async with anyio.create_task_group() as tg:
        tg.start_soon(fastapi_app, scope, fastapi_q.get, fastapi_send)
        tg.start_soon(mcp_app, scope, mcp_q.get, mcp_send)

        try:
            await asyncio.wait_for(fastapi_ready.wait(), timeout=30)
        except asyncio.TimeoutError:
            raise RuntimeError("FastAPI startup timed out after 30 seconds")
        try:
            await asyncio.wait_for(mcp_ready.wait(), timeout=30)
        except asyncio.TimeoutError:
            raise RuntimeError("FastMCP startup timed out after 30 seconds")
        await send({"type": "lifespan.startup.complete"})

        shutdown = await receive()
        await fastapi_q.put(shutdown)
        await mcp_q.put(shutdown)

        await fastapi_done.wait()
        await mcp_done.wait()
        await send({"type": "lifespan.shutdown.complete"})


class MCPMiddleware:
    """Top-level ASGI app: routes /mcp/* to FastMCP, everything else to FastAPI."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await _dual_lifespan(self._app, _mcp_starlette, scope, receive, send)
            return

        if scope["type"] != "http":
            return await self._app(scope, receive, send)

        path: str = scope.get("path", "")
        if path.startswith("/mcp/") or path == "/mcp":
            await _mcp_auth(scope, receive, send)
            return

        await self._app(scope, receive, send)


app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
)

init_cors(app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logger = logging.getLogger(__name__)

    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be set in environment or .env file")

    if not settings.COOKIE_SECURE:
        logger.warning("COOKIE_SECURE is False — refresh tokens will be sent over HTTP. Set True in production.")

    if not settings.CORS_ORIGINS:
        logger.warning("CORS_ORIGINS is empty — no cross-origin requests will be allowed. Set explicitly in production.")

    if settings.CORS_CREDENTIALS and "*" in settings.CORS_ORIGINS:
        logger.warning("CORS_CREDENTIALS=True with CORS_ORIGINS=['*'] — allows any origin to make credentialed requests")

    db_gen = get_db()
    db = next(db_gen)
    try:
        await create_superuser(db)
    finally:
        db_gen.close()
    yield
    await mcp_pool.close_all()


app.router.lifespan_context = lifespan

app.include_router(auth.router)
app.include_router(blog.router)
app.include_router(cuan.router)
app.include_router(ngakak.router)
app.include_router(chat.router)
app.include_router(files.router)


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.API_TITLE}"}


# Wrap FastAPI — must come after full app configuration
app = MCPMiddleware(app)  # type: ignore[assignment]
