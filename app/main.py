from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.middleware.cors import init_cors
from app.routers import auth, blog, ngakak, cuan
from app.utils.database import get_db
from app.utils.superuser import create_superuser
from app.core.config import settings
from app.mcp.server import create_mcp_asgi_app
from starlette.types import ASGIApp, Receive, Scope, Send

_mcp_inner = create_mcp_asgi_app()


class MCPMiddleware:
    """Intercepts /mcp/{token} paths before FastAPI routing, avoiding Starlette prefix stripping."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            path: str = scope.get("path", "")
            if path.startswith("/mcp/") or path == "/mcp":
                await _mcp_inner(scope, receive, send)
                return
        await self._app(scope, receive, send)


app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
)

# Initialize CORS
init_cors(app)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db = next(get_db())
    create_superuser(db)
    yield
    # Shutdown
    pass

app.router.lifespan_context = lifespan

# Include routers
app.include_router(auth.router)
app.include_router(blog.router)
app.include_router(cuan.router)
app.include_router(ngakak.router)

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.API_TITLE}"}


# Wrap FastAPI with MCP middleware — must be after app is fully configured
app = MCPMiddleware(app)  # type: ignore[assignment]