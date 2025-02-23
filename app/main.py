from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import auth, blog
from app.utils.database import engine, get_db
from app.utils.superuser import create_superuser

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db = next(get_db())
    create_superuser(db)
    yield
    # Shutdown
    pass

app = FastAPI(
    title="yupi - yudopr API",
    description="API for many yudopr webapp projects",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(auth.router)
app.include_router(blog.router)

@app.get("/")
async def root():
    return {"message": "Welcome to yupi - yudopr API"} 