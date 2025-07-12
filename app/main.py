from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.middleware.cors import init_cors
from app.routers import auth, blog, ngakak, cuan
from app.utils.database import get_db
from app.utils.superuser import create_superuser
from app.core.config import settings

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