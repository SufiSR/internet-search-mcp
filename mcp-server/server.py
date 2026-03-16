"""
FastAPI application entry point.

Exposes:
  - REST API (POST /search, /fetch, /crawl, /browse, GET /health)
  - MCP server (mounted at /mcp, streamable-HTTP + SSE transport)

Both layers share the same underlying logic modules. Authentication is applied
to REST routes via FastAPI dependencies and to the MCP mount via ASGI middleware.
"""

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import MCPAuthMiddleware, verify_api_key
from config import settings
from fetch import fetch_page
from mcp_handler import get_mcp_asgi_app, mcp as mcp_instance
from scrape import scrape_page
from search import search_web
from tools import BrowseResult, PageResult, browse

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            }
        },
        "root": {
            "handlers": ["console"],
            "level": settings.log_level.upper(),
        },
    }
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

# Build the MCP sub-app first so its session manager is initialised before the
# lifespan context below references it.
mcp_app = get_mcp_asgi_app()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # StreamableHTTPSessionManager requires its anyio task group to be running
    # before it can handle requests.  Starlette 0.52 does not propagate the
    # lifespan of mounted sub-apps to the parent, so we start it here instead.
    async with mcp_instance.session_manager.run():
        logger.info("MCP session manager started")
        yield
    logger.info("MCP session manager stopped")


app = FastAPI(
    title="AI Browsing MCP Stack",
    description=(
        "Self-hosted web browsing backend exposing search, fetch, crawl, and browse "
        "tools via both a REST API and a native MCP server."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# MCP server — mounted at /mcp with auth middleware
# ---------------------------------------------------------------------------

app.mount("/mcp", MCPAuthMiddleware(mcp_app))

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str


class FetchRequest(BaseModel):
    url: str


class CrawlRequest(BaseModel):
    url: str


class BrowseRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Health endpoint — no authentication required
# ---------------------------------------------------------------------------


@app.api_route("/health", methods=["GET", "HEAD"])
async def health() -> dict:
    """
    Liveness check.

    Returns 200 with service status. Supports GET and HEAD for load balancers
    and Docker healthchecks (wget --spider uses HEAD).
    """
    return {"status": "ok", "service": "browsing-mcp"}


# ---------------------------------------------------------------------------
# REST endpoints — all require API key authentication
# ---------------------------------------------------------------------------


@app.post("/search")
async def search_endpoint(
    request: SearchRequest,
    _: str = Depends(verify_api_key),
) -> dict:
    """
    Search the web via SearXNG and return structured results.

    Returns a list of results with title, url, and snippet for each.
    """
    logger.info("REST /search called with query: %r", request.query)
    results = await search_web(request.query)

    return {
        "results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet}
            for r in results
        ]
    }


@app.post("/fetch")
async def fetch_endpoint(
    request: FetchRequest,
    _: str = Depends(verify_api_key),
) -> JSONResponse:
    """
    Fetch a URL and return its content as markdown using fast extraction.

    Returns HTTP 200 with content on success, or HTTP 422 with an error
    message if the page could not be extracted.
    """
    logger.info("REST /fetch called for URL: %s", request.url)
    content = await fetch_page(request.url)

    if content is None:
        return JSONResponse(
            status_code=422,
            content={
                "error": "Could not extract content from this URL. Try /crawl instead.",
                "code": "FETCH_FAILED",
                "url": request.url,
            },
        )

    return JSONResponse(content={"url": request.url, "content": content})


@app.post("/crawl")
async def crawl_endpoint(
    request: CrawlRequest,
    _: str = Depends(verify_api_key),
) -> JSONResponse:
    """
    Scrape a URL using Firecrawl and return markdown content.

    Suitable for JavaScript-heavy or bot-protected pages. Returns HTTP 422
    if Firecrawl cannot extract content.
    """
    logger.info("REST /crawl called for URL: %s", request.url)
    content = await scrape_page(request.url)

    if content is None:
        return JSONResponse(
            status_code=422,
            content={
                "error": "Firecrawl could not extract content from this URL.",
                "code": "FETCH_FAILED",
                "url": request.url,
            },
        )

    return JSONResponse(content={"url": request.url, "content": content})


@app.post("/browse")
async def browse_endpoint(
    request: BrowseRequest,
    _: str = Depends(verify_api_key),
) -> dict:
    """
    Run the full automatic browsing pipeline for a query.

    Combines search, BM25 ranking, and concurrent page fetching with
    Firecrawl fallback. Returns enriched results with extracted content.
    """
    logger.info("REST /browse called with query: %r", request.query)
    result: BrowseResult = await browse(request.query)

    return {
        "query": result.query,
        "results": [_serialize_page_result(page) for page in result.results],
    }


def _serialize_page_result(page: PageResult) -> dict:
    """
    Convert a PageResult dataclass into a JSON-serializable dict.

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
