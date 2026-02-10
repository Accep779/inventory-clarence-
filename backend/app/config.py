"""
Configuration settings for the Inventory Clearance Agent.
Loads from environment variables with validation.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Inventory Clearance Agent"
    DEBUG: bool = False
    HOST: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    SECRET_KEY: str

    # Database
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"

    # Shopify OAuth
    SHOPIFY_API_KEY: str
    SHOPIFY_API_SECRET: str
    SHOPIFY_SCOPES: str = "read_products,read_orders,read_customers,write_products"
    SHOPIFY_API_VERSION: str = "2025-01"

    # BigCommerce OAuth
    BIGCOMMERCE_CLIENT_ID: str | None = None
    BIGCOMMERCE_CLIENT_SECRET: str | None = None

    # Anthropic (Claude)
    ANTHROPIC_API_KEY: str

    # Optional: Email/SMS Integrations
    KLAVIYO_API_KEY: str | None = None
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_PHONE_NUMBER: str | None = None
    
    # Slack Alerting
    SLACK_WEBHOOK_URL: str | None = None
    SLACK_ALERTS_CHANNEL: str = "#cephly-alerts-critical"

    # Token Vault (Auth0 Pattern - Encrypted Credential Storage)
    # REQUIRED in production - generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    TOKEN_ENCRYPTION_KEY: str | None = None
    USE_TOKEN_VAULT: bool = True  # Default to secure storage
    
    def validate_production_settings(self):
        """Validate critical settings for production deployment."""
        if not self.DEBUG and not self.TOKEN_ENCRYPTION_KEY:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY is required in production. "
                "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings loader with production validation."""
    settings = Settings()
    # Validate critical settings when not in debug mode
    if not settings.DEBUG:
        settings.validate_production_settings()
    return settings
