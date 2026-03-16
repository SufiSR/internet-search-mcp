"""
Fast HTML fetch and content extraction.

Primary content retrieval method. Downloads a page with httpx, extracts the
main article content using readability-lxml, and converts it to markdown.

Returns None when:
  - The network request fails or times out
  - The extracted content is below the minimum length threshold (500 chars),
    which signals a JavaScript-rendered page or paywall that fast fetch cannot
    handle — the caller should fall back to Firecrawl.

Playwright placeholder:
  render_with_browser() is stubbed here as the documented integration point
  for a future headless browser renderer. When implemented, the fallback chain
  in tools.py will extend to: fetch → Firecrawl → browser render.
"""

import logging

import httpx
from markdownify import markdownify
from readability import Document

from config import settings

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 15
MIN_CONTENT_LENGTH = 500

# Realistic browser user-agent to reduce bot-detection rejections
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_page(url: str) -> str | None:
    """
    Download a page and extract readable markdown content.

    Args:
        url: The URL to fetch.

    Returns:
        Extracted markdown string, or None if extraction fails or content
        is below the minimum length threshold.
    """
    logger.debug("Fetching page: %s", url)

    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.TimeoutException:
        logger.warning("Fetch timed out for URL: %s", url)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP %s when fetching URL: %s", exc.response.status_code, url)
        return None
    except httpx.RequestError as exc:
        logger.warning("Request error fetching URL %s: %s", url, exc)
        return None

    return _extract_markdown(html, url)


def _extract_markdown(html: str, url: str) -> str | None:
    """
    Parse HTML with readability-lxml and convert the main content to markdown.

    Args:
        html: Raw HTML string.
        url:  Source URL (used only for logging).

    Returns:
        Markdown string, or None if content is below the minimum threshold.
    """
    try:
        doc = Document(html)
        content_html = doc.summary(html_partial=True)
    except Exception as exc:
        logger.warning("readability failed for %s: %s", url, exc)
        return None

    try:
        markdown = markdownify(content_html, heading_style="ATX", strip=["a"])
    except Exception as exc:
        logger.warning("markdownify failed for %s: %s", url, exc)
        return None

    # Collapse excessive whitespace produced by markdownify
    lines = [line.rstrip() for line in markdown.splitlines()]
    cleaned = "\n".join(lines).strip()

    if len(cleaned) < MIN_CONTENT_LENGTH:
        logger.debug(
            "Content below threshold (%d chars) for URL: %s — triggering fallback",
            len(cleaned),
            url,
        )
        return None

    # Enforce maximum content length to avoid huge API responses
    if len(cleaned) > settings.max_content_length:
        cleaned = cleaned[: settings.max_content_length]
        logger.debug("Truncated content to %d chars for URL: %s", settings.max_content_length, url)

    return cleaned


def render_with_browser(url: str) -> None:
    """
    Placeholder for future headless browser rendering.

    When implemented, this function will launch a Playwright browser session,
    render the page (including JavaScript), and return the rendered HTML for
    further extraction.

    Integration point in tools.py:
        fetch_page(url) fails
        → scrape_page(url) fails      [Firecrawl]
        → render_with_browser(url)    [this function, future]

    To implement:
      1. Add a playwright-renderer service to docker-compose.yml (placeholder
         comment already exists).
      2. Replace this function body with an httpx call to that service.
      3. Pass the rendered HTML through _extract_markdown().

    Args:
        url: The URL that requires browser rendering.

    Returns:
        None (not yet implemented).
    """
    logger.warning(
        "render_with_browser() called for %s but browser rendering is not yet implemented. "
        "Add a Playwright renderer service and implement this function to enable it.",
        url,
    )
    return None
