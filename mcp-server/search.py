"""
SearXNG search client.

Provides a single async function that queries SearXNG and returns structured
search results. All network errors are caught and logged — callers receive an
empty list rather than an exception propagating to the API boundary.
"""

import logging
from dataclasses import dataclass

import httpx

from config import settings

logger = logging.getLogger(__name__)

SEARXNG_TIMEOUT_SECONDS = 10


@dataclass
class SearchResult:
    """A single search result returned by SearXNG."""

    title: str
    url: str
    snippet: str


async def search_web(query: str, count: int | None = None) -> list[SearchResult]:
    """
    Search the web via SearXNG and return structured results.

    Args:
        query: The search query string.
        count: Maximum number of results to return. Defaults to settings.result_count.

    Returns:
        List of SearchResult objects. Empty list on any failure.
    """
    if count is None:
        count = settings.result_count

    params = {
        "q": query,
        "format": "json",
        "pageno": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=SEARXNG_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{settings.searxng_url}/search", params=params)
            response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("SearXNG request timed out for query: %r", query)
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning("SearXNG returned HTTP %s for query: %r", exc.response.status_code, query)
        return []
    except httpx.RequestError as exc:
        logger.warning("SearXNG request failed: %s", exc)
        return []

    try:
        data = response.json()
        raw_results = data.get("results", [])
    except Exception as exc:
        logger.warning("Failed to parse SearXNG response: %s", exc)
        return []

    results = []

    for item in raw_results[:count]:
        title = item.get("title") or ""
        url = item.get("url") or ""
        snippet = item.get("content") or ""

        if not url:
            continue

        results.append(SearchResult(title=title, url=url, snippet=snippet))

    logger.info("SearXNG returned %d results for query: %r", len(results), query)
    return results
