from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def init_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
        allow_credentials=settings.CORS_CREDENTIALS,
        max_age=settings.CORS_MAX_AGE,
    ) 