"""
MCP server definition.

Registers the four browsing tools with the official Anthropic MCP SDK and
returns the ASGI application that server.py mounts at /mcp.

The tools registered here are thin wrappers around the same underlying
functions used by the REST API — no logic duplication.

MCP transport:
  The FastMCP instance is configured for streamable-HTTP transport, which
  supports both POST (request/response) and GET (SSE stream) at the same path.
  LibreChat connects via SSE; n8n and curl can use plain POST.
"""

import logging

from mcp.server.fastmcp import FastMCP

from fetch import fetch_page
from scrape import scrape_page
from search import search_web
from tools import BrowseResult, PageResult
from tools import browse as run_browse_pipeline

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="ai-browsing-mcp",
    instructions=(
        "This server provides web browsing tools for AI agents. "
        "Use 'search' for exploratory queries, 'fetch' for direct fast page retrieval, "
        "'crawl' for JavaScript-heavy or difficult pages, and 'browse' for an automatic "
        "pipeline that combines search, ranking, and content extraction."
    ),
)


@mcp.tool()
async def search(query: str) -> dict:
    """
    Search the web and return a list of results (title, url, snippet).

    Use this tool when you want to discover relevant URLs for a topic
    without fetching the full page content yet.

    Args:
        query: The search query.

    Returns:
        A dict with a 'results' list, each item containing title, url, snippet.
    """
    logger.info("MCP tool 'search' called with query: %r", query)
    results = await search_web(query)

    return {
        "results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet}
            for r in results
        ]
    }


@mcp.tool()
async def fetch(url: str) -> dict:
    """
    Fetch a URL and return its content as markdown using fast extraction.

    Suitable for most standard web pages. Returns an error message if the
    page cannot be extracted (e.g. JavaScript-rendered, paywalled). Use
    'crawl' as a fallback for difficult pages.

    Args:
        url: The full URL to fetch.

    Returns:
        A dict with 'content' (markdown string) or 'error' on failure.
    """
    logger.info("MCP tool 'fetch' called for URL: %s", url)
    content = await fetch_page(url)

    if content is None:
        return {
            "error": "Could not extract content from this URL. Try 'crawl' instead.",
            "code": "FETCH_FAILED",
            "url": url,
        }

    return {"url": url, "content": content}


@mcp.tool()
async def crawl(url: str) -> dict:
    """
    Scrape a URL using Firecrawl (headless browser) and return markdown content.

    Use this for JavaScript-heavy pages, sites with bot protection, or any
    URL where 'fetch' failed or returned insufficient content.

    Args:
        url: The full URL to scrape.

    Returns:
        A dict with 'content' (markdown string) or 'error' on failure.
    """
    logger.info("MCP tool 'crawl' called for URL: %s", url)
    content = await scrape_page(url)

    if content is None:
        return {
            "error": "Firecrawl could not extract content from this URL.",
            "code": "FETCH_FAILED",
            "url": url,
        }

    return {"url": url, "content": content}


@mcp.tool()
async def browse(query: str) -> dict:
    """
    Automatically search, rank, and fetch the best results for a query.

    This is the all-in-one browsing tool. It:
      1. Searches SearXNG for relevant URLs
      2. Re-ranks results with BM25
      3. Fetches the top 3 URLs concurrently
      4. Falls back to Firecrawl if fast fetch fails

    Use this when you want comprehensive content for a query without
    deciding which URL to visit manually.

    Args:
        query: The search query to research.

    Returns:
        A dict with 'query' and a 'results' list containing enriched page data.
    """
    logger.info("MCP tool 'browse' called with query: %r", query)

    result: BrowseResult = await run_browse_pipeline(query)

    return {
        "query": result.query,
        "results": [_serialize_page_result(page) for page in result.results],
    }


def _serialize_page_result(page: PageResult) -> dict:
    """
    Convert a PageResult dataclass to a JSON-serializable dict.

    Args:
        page: PageResult from the browse pipeline.

    Returns:
        Dict with title, url, snippet, content, and source fields.
    """
    return {
        "title": page.title,
        "url": page.url,
        "snippet": page.snippet,
        "content": page.content,
        "source": page.source,
    }


def get_mcp_asgi_app():
    """
    Return the MCP ASGI application for mounting in server.py.

    Returns:
        Starlette-compatible ASGI app from FastMCP.
    """
    return mcp.streamable_http_app()
