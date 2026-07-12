"""Project configuration management"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""
    
    # Database configuration
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        ""
    )
    
    # Database connection pool settings
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_RECYCLE: int = 300
    DATABASE_POOL_PRE_PING: bool = True
    
    # OpenAI configuration
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    
    # API configuration
    API_VERSION: str = "v1"
    API_TITLE: str = "NL2SQL Backend"
    API_DEBUG: bool = os.environ.get("API_DEBUG", "false").lower() == "true"
    
    # CORS settings
    CORS_ORIGINS: list = ["*"]

    # Local development identity (simulates a logged-in user until real auth exists)
    APP_USER_ID: str = os.environ.get("APP_USER_ID", "local-user")
    APP_USER_NAME: str = os.environ.get("APP_USER_NAME", "Local User")
    APP_USER_ROLE: str = os.environ.get("APP_USER_ROLE", "analyst")
    
    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration"""
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is required")
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")


# Global settings instance
settings = Settings()
settings.validate()
