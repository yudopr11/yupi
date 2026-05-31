import logging
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800

    # JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # Superuser credentials
    SUPERUSER_USERNAME: str = "admin"
    SUPERUSER_EMAIL: str = "admin@example.com"
    SUPERUSER_PASSWORD: str = "admin123"

    # Cookie settings
    COOKIE_SECURE: bool = False  # Set True in production (requires HTTPS)

    # CORS Settings
    # WARNING: In production, explicitly set CORS_ORIGINS to your frontend domain(s).
    # Never use ["*"] with CORS_CREDENTIALS=True in production.
    CORS_ORIGINS: List[str] = []
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_MAX_AGE: int = 600

    # API Info
    API_TITLE: str = "yupi - yudopr API"
    API_DESCRIPTION: str = "API for many yudopr webapp projects"
    API_VERSION: str = "1.0.0"

    # OpenAI API Key
    OPENAI_API_KEY: str = ""
    
    # MiMo LLM settings (defaults, can be overridden per-user in DB)
    MIMO_API_KEY: str = ""
    MIMO_BASE_URL: str = "https://token-plan-sgp.xiaomimimo.com/anthropic"
    MIMO_MODEL: str = "mimo-v2.5"

    # RustFS (S3-compatible) settings
    RUSTFS_ENDPOINT: str = "http://localhost:9000"
    RUSTFS_ACCESS_KEY: str = ""
    RUSTFS_SECRET_KEY: str = ""
    RUSTFS_BUCKET: str = "yupi-uploads"
    RUSTFS_REGION: str = "us-east-1"

    # Ngakak settings
    NGAKAK_TRUST_X_FORWARDED_FOR: bool = False  # If True, trust X-Forwarded-For header for client IP

    # MCP settings
    MCP_DNS_REBINDING_PROTECTION: bool = False  # Enable DNS rebinding protection for MCP server

    # Email settings - Gmail
    MAIL_USERNAME: str = "your.email@gmail.com"  # Replace with your Gmail address
    MAIL_PASSWORD: str = "your-app-password"     # Replace with your App Password
    MAIL_FROM: str = "your.email@gmail.com"      # Replace with your Gmail address
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_USE_CREDENTIALS: bool = True
    MAIL_VALIDATE_CERTS: bool = True

    @model_validator(mode="after")
    def _check_cors_credentials_wildcard(self) -> "Settings":
        if self.CORS_CREDENTIALS and ("*" in self.CORS_ORIGINS):
            logger.warning(
                "CORS_CREDENTIALS is True but CORS_ORIGINS contains '*'. "
                "This is insecure for production. Restrict CORS_ORIGINS to explicit origins."
            )
        return self

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings() 