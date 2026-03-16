"""
Firecrawl scraping client.

Fallback content retrieval method for pages that fast fetch cannot handle
(JavaScript-heavy sites, paywalls, bot-detection protected pages).

Firecrawl runs its own headless browser (via the playwright-service container)
and returns clean markdown directly. This makes it slower but more capable
than the fast fetch path.
"""

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

FIRECRAWL_TIMEOUT_SECONDS = 30


async def scrape_page(url: str) -> str | None:
    """
    Scrape a page using Firecrawl and return markdown content.

    Calls the Firecrawl /v1/scrape endpoint with markdown format requested.
    Returns None on any failure so that callers can handle the fallback
    gracefully rather than receiving an exception.

    Args:
        url: The URL to scrape.

    Returns:
        Markdown string from Firecrawl, or None on failure.
    """
    logger.debug("Scraping page with Firecrawl: %s", url)

    payload = {
        "url": url,
        "formats": ["markdown"],
    }

    try:
        async with httpx.AsyncClient(timeout=FIRECRAWL_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{settings.firecrawl_url}/v1/scrape",
                json=payload,
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("Firecrawl timed out for URL: %s", url)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Firecrawl returned HTTP %s for URL: %s",
            exc.response.status_code,
            url,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning("Firecrawl request error for URL %s: %s", url, exc)
        return None

    try:
        data = response.json()
        markdown = _extract_markdown_from_response(data)
    except Exception as exc:
        logger.warning("Failed to parse Firecrawl response for %s: %s", url, exc)
        return None

    if not markdown:
        logger.warning("Firecrawl returned empty content for URL: %s", url)
        return None

    # Enforce maximum content length
    if len(markdown) > settings.max_content_length:
        markdown = markdown[: settings.max_content_length]
        logger.debug("Truncated Firecrawl content to %d chars for URL: %s", settings.max_content_length, url)

    logger.info("Firecrawl successfully scraped %d chars from: %s", len(markdown), url)
    return markdown


def _extract_markdown_from_response(data: dict) -> str | None:
    """
    Pull the markdown content out of the Firecrawl API response.

    Firecrawl wraps its response in a data envelope:
      { "success": true, "data": { "markdown": "...", ... } }

    Args:
        data: Parsed JSON response from Firecrawl.

    Returns:
        Markdown string, or None if the expected fields are absent.
    """
    if not data.get("success"):
        return None

    inner = data.get("data") or {}
    markdown = inner.get("markdown") or ""

    return markdown.strip() or None
