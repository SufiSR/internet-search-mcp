"""
Application configuration.

All settings are read from environment variables. No module in this codebase
should read os.environ directly — import `settings` from this module instead.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """
    Typed configuration model.

    Pydantic-settings automatically reads values from environment variables
    (case-insensitive). Defaults are provided for all non-secret fields.
    """

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore env vars not declared in this model — other services (Firecrawl,
        # SearXNG) share the same environment and have their own variables.
        extra="ignore",
    )

    # Security
    api_key: str

    # Internal service URLs
    searxng_url: str = "http://searxng:8080"
    firecrawl_url: str = "http://firecrawl-api:3002"

    # Search and scraping limits
    result_count: int = 10
    scrape_count: int = 3
    max_content_length: int = 50000

    # Rate limiting (in-memory, per API key, per minute)
    rate_limit_per_minute: int = 30

    # Logging
    log_level: str = "INFO"


# Module-level singleton — import this everywhere
settings = Settings()
