"""
Tests for the browse pipeline (tools.py).

All I/O functions (search_web, fetch_page, scrape_page) are patched with
unittest.mock to avoid any real network calls and give precise control over
each fallback scenario.
"""

from unittest.mock import AsyncMock, patch

import pytest

from search import SearchResult
from tools import BrowseResult, browse


SAMPLE_RESULTS = [
    SearchResult(title="Python asyncio", url="https://docs.python.org/asyncio", snippet="async library"),
    SearchResult(title="Real Python async", url="https://realpython.com/async", snippet="tutorial"),
    SearchResult(title="Gardening", url="https://example.com/garden", snippet="tomatoes"),
]

LONG_CONTENT = "# Article\n\n" + ("This is sample content. " * 30)


class TestBrowsePipeline:
    @pytest.mark.asyncio
    async def test_fetch_succeeds_returns_fetch_source(self):
        """When fetch_page succeeds, result source should be 'fetch'."""
        with (
            patch("tools.search_web", new=AsyncMock(return_value=SAMPLE_RESULTS)),
            patch("tools.fetch_page", new=AsyncMock(return_value=LONG_CONTENT)),
        ):
            result: BrowseResult = await browse("python async")

        assert len(result.results) > 0
        for page in result.results:
            assert page.source == "fetch"
            assert page.content == LONG_CONTENT

    @pytest.mark.asyncio
    async def test_fetch_fails_firecrawl_succeeds(self):
        """When fetch_page returns None, scrape_page should be used."""
        with (
            patch("tools.search_web", new=AsyncMock(return_value=SAMPLE_RESULTS)),
            patch("tools.fetch_page", new=AsyncMock(return_value=None)),
            patch("tools.scrape_page", new=AsyncMock(return_value=LONG_CONTENT)),
        ):
            result: BrowseResult = await browse("python async")

        assert len(result.results) > 0
        for page in result.results:
            assert page.source == "firecrawl"
            assert page.content == LONG_CONTENT

    @pytest.mark.asyncio
    async def test_both_fetch_methods_fail_marks_unavailable(self):
        """When both fetch_page and scrape_page return None, source is 'unavailable'."""
        with (
            patch("tools.search_web", new=AsyncMock(return_value=SAMPLE_RESULTS)),
            patch("tools.fetch_page", new=AsyncMock(return_value=None)),
            patch("tools.scrape_page", new=AsyncMock(return_value=None)),
        ):
            result: BrowseResult = await browse("python async")

        assert len(result.results) > 0
        for page in result.results:
            assert page.source == "unavailable"
            assert page.content is None

    @pytest.mark.asyncio
    async def test_empty_search_results_returns_empty_browse_result(self):
        with patch("tools.search_web", new=AsyncMock(return_value=[])):
            result: BrowseResult = await browse("no results query")

        assert result.query == "no results query"
        assert result.results == []

    @pytest.mark.asyncio
    async def test_query_preserved_in_result(self):
        with (
            patch("tools.search_web", new=AsyncMock(return_value=SAMPLE_RESULTS)),
            patch("tools.fetch_page", new=AsyncMock(return_value=LONG_CONTENT)),
        ):
            result: BrowseResult = await browse("my specific query")

        assert result.query == "my specific query"

    @pytest.mark.asyncio
    async def test_result_count_capped_by_scrape_count(self):
        """Browse should return at most scrape_count results."""
        from config import settings

        with (
            patch("tools.search_web", new=AsyncMock(return_value=SAMPLE_RESULTS)),
            patch("tools.fetch_page", new=AsyncMock(return_value=LONG_CONTENT)),
        ):
            result: BrowseResult = await browse("python")

        assert len(result.results) <= settings.scrape_count

    @pytest.mark.asyncio
    async def test_mixed_fetch_sources(self):
        """First URL fetches OK, second requires Firecrawl, third fails entirely."""
        fetch_responses = [LONG_CONTENT, None, None]
        scrape_responses = [None, LONG_CONTENT, None]

        fetch_mock = AsyncMock(side_effect=fetch_responses)
        scrape_mock = AsyncMock(side_effect=scrape_responses)

        with (
            patch("tools.search_web", new=AsyncMock(return_value=SAMPLE_RESULTS)),
            patch("tools.fetch_page", new=fetch_mock),
            patch("tools.scrape_page", new=scrape_mock),
        ):
            result: BrowseResult = await browse("python")

        sources = [page.source for page in result.results]
        assert "fetch" in sources
        assert "firecrawl" in sources
        assert "unavailable" in sources
