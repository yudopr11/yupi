from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5433/yupi_db"

    # JWT settings
    SECRET_KEY: str = "your-super-secret-key-that-should-be-very-long-and-random"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # Superuser credentials
    SUPERUSER_USERNAME: str = "admin"
    SUPERUSER_EMAIL: str = "admin@example.com"
    SUPERUSER_PASSWORD: str = "admin123"

    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_MAX_AGE: int = 600

    # API Info
    API_TITLE: str = "yupi - yudopr API"
    API_DESCRIPTION: str = "API for many yudopr webapp projects"
    API_VERSION: str = "1.0.0"

    # OpenAI API Key
    OPENAI_API_KEY: str = "sk-proj-1234567890"
    
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

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 