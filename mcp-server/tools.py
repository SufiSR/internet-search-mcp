"""
Browse pipeline orchestration.

This module assembles the full automatic browsing pipeline used by both
the REST /browse endpoint and the MCP browse tool:

  1. search_web()       — query SearXNG for candidate URLs
  2. rank_results()     — BM25 re-ranking to select the top N
  3. asyncio.gather()   — fetch all top URLs concurrently
  4. per-URL fallback   — fetch_page → scrape_page → unavailable

The total pipeline has a 45-second budget enforced via asyncio.wait_for.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from config import settings
from fetch import fetch_page
from ranking import rank_results
from scrape import scrape_page
from search import SearchResult, search_web

logger = logging.getLogger(__name__)

BROWSE_TOTAL_TIMEOUT_SECONDS = 45

ContentSource = Literal["fetch", "firecrawl", "unavailable"]


@dataclass
class PageResult:
    """Enriched result containing search metadata and extracted page content."""

    title: str
    url: str
    snippet: str
    content: str | None
    source: ContentSource


@dataclass
class BrowseResult:
    """Full browse pipeline output."""

    query: str
    results: list[PageResult]


async def browse(query: str) -> BrowseResult:
    """
    Execute the full automatic browsing pipeline for a query.

    Searches, ranks, and fetches content concurrently, falling back from
    fast-fetch to Firecrawl per URL as needed.

    Args:
        query: The search query to process.

    Returns:
        BrowseResult containing the query and enriched page results.
    """
    try:
        result = await asyncio.wait_for(
            _run_browse_pipeline(query),
            timeout=BROWSE_TOTAL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Browse pipeline timed out after %ds for query: %r", BROWSE_TOTAL_TIMEOUT_SECONDS, query)
        result = BrowseResult(query=query, results=[])

    return result


async def _run_browse_pipeline(query: str) -> BrowseResult:
    """
    Internal pipeline implementation (no timeout wrapper).

    Separated from browse() so asyncio.wait_for wraps the full pipeline
    cleanly from the outside.
    """
    logger.info("Starting browse pipeline for query: %r", query)

    search_results = await search_web(query, count=settings.result_count)

    if not search_results:
        logger.warning("Browse: no search results returned for query: %r", query)
        return BrowseResult(query=query, results=[])

    top_results = rank_results(search_results, query, top_n=settings.scrape_count)
    logger.info("Browse: selected %d URLs to fetch", len(top_results))

    # Fetch all top URLs concurrently
    page_results = await asyncio.gather(
        *[_fetch_with_fallback(result) for result in top_results]
    )

    return BrowseResult(query=query, results=list(page_results))


async def _fetch_with_fallback(search_result: SearchResult) -> PageResult:
    """
    Attempt to retrieve page content with automatic fallback.

    Fallback chain:
      1. fetch_page()  — fast HTTP fetch + readability extraction
      2. scrape_page() — Firecrawl (headless browser)
      3. unavailable   — both methods failed

    Args:
        search_result: A ranked SearchResult whose URL will be fetched.

    Returns:
        PageResult with content and the source that provided it.
    """
    url = search_result.url

    # Attempt 1: fast fetch
    content = await fetch_page(url)

    if content is not None:
        logger.debug("fetch_page succeeded for: %s", url)
        return PageResult(
            title=search_result.title,
            url=url,
            snippet=search_result.snippet,
            content=content,
            source="fetch",
        )

    # Attempt 2: Firecrawl fallback
    logger.debug("fetch_page returned None for %s — trying Firecrawl", url)
    content = await scrape_page(url)

    if content is not None:
        logger.debug("scrape_page succeeded for: %s", url)
        return PageResult(
            title=search_result.title,
            url=url,
            snippet=search_result.snippet,
            content=content,
            source="firecrawl",
        )

    # Both methods failed
    logger.warning("All fetch methods failed for URL: %s", url)
    return PageResult(
        title=search_result.title,
        url=url,
        snippet=search_result.snippet,
        content=None,
        source="unavailable",
    )
