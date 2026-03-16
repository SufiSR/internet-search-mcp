"""
Shared test fixtures.

All fixtures are async-compatible (pytest-asyncio in auto mode).
External HTTP calls are mocked via respx — no real network access occurs
during the test suite.
"""

import os

import pytest

# Set environment variables before any application module is imported.
# This prevents pydantic-settings from raising a validation error for
# the required API_KEY field.
os.environ.setdefault("API_KEY", "test-api-key-fixture")
os.environ.setdefault("SEARXNG_URL", "http://searxng-mock:8080")
os.environ.setdefault("FIRECRAWL_URL", "http://firecrawl-mock:3002")

from search import SearchResult  # noqa: E402 — must be after env setup


TEST_API_KEY = "test-api-key-fixture"
VALID_AUTH_HEADER = {"X-API-Key": TEST_API_KEY}


@pytest.fixture()
def sample_search_results() -> list[SearchResult]:
    """Three synthetic search results for use in ranking and pipeline tests."""
    return [
        SearchResult(
            title="Python asyncio documentation",
            url="https://docs.python.org/asyncio",
            snippet="asyncio is a library to write concurrent code using the async/await syntax.",
        ),
        SearchResult(
            title="Understanding Python async/await",
            url="https://realpython.com/async-io-python",
            snippet="This tutorial gives you a solid understanding of Python's async features.",
        ),
        SearchResult(
            title="Unrelated result about gardening",
            url="https://example.com/gardening",
            snippet="How to grow tomatoes in your backyard garden.",
        ),
    ]


@pytest.fixture()
def long_markdown_content() -> str:
    """Markdown content well above the 500-char extraction threshold."""
    return "# Test Page\n\n" + ("This is sample content for testing purposes. " * 20)


@pytest.fixture()
def short_markdown_content() -> str:
    """Content below the 500-char threshold — should trigger fetch fallback."""
    return "Too short."
