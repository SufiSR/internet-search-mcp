"""
Authentication and rate limiting.

Provides:
  - verify_api_key()     FastAPI dependency for REST routes
  - RateLimiter          In-memory sliding-window rate limiter (per API key)
  - MCPAuthMiddleware    ASGI middleware that applies auth to the /mcp mount

Rate limiter note:
  The current implementation uses an in-memory dictionary. This is correct for
  single-process deployments (one Uvicorn worker). For multi-worker or
  multi-container deployments, replace with a Redis-backed implementation using
  a sorted set per key (ZREMRANGEBYSCORE + ZADD + ZCARD pattern).
"""

import logging
import time
from collections import defaultdict
from typing import Awaitable, Callable

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from config import settings

logger = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class RateLimiter:
    """
    In-memory sliding-window rate limiter.

    Tracks request timestamps per API key. Requests older than 60 seconds
    are evicted on each check to keep memory bounded.
    """

    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        # Maps api_key -> list of unix timestamps (floats)
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, api_key: str) -> bool:
        """
        Return True if the request is within the rate limit, False otherwise.

        Evicts timestamps older than 60 seconds before checking.
        """
        now = time.monotonic()
        window_start = now - 60.0

        timestamps = self._windows[api_key]

        # Remove timestamps outside the current window
        self._windows[api_key] = [ts for ts in timestamps if ts > window_start]

        if len(self._windows[api_key]) >= self._limit:
            return False

        self._windows[api_key].append(now)
        return True


# Single shared limiter instance
_rate_limiter = RateLimiter(limit_per_minute=settings.rate_limit_per_minute)


async def verify_api_key(api_key: str | None = Security(_API_KEY_HEADER)) -> str:
    """
    FastAPI dependency that validates the X-API-Key header.

    Raises HTTP 401 if the key is missing or invalid.
    Raises HTTP 429 if the key has exceeded its rate limit.

    Returns the validated API key string on success.
    """
    if not api_key or api_key != settings.api_key:
        logger.warning("Rejected request: invalid or missing API key")
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid or missing API key", "code": "UNAUTHORIZED"},
        )

    if not _rate_limiter.is_allowed(api_key):
        logger.warning("Rejected request: rate limit exceeded for key ending in ...%s", api_key[-4:])
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "code": "RATE_LIMITED"},
        )

    return api_key


class MCPAuthMiddleware:
    """
    ASGI middleware that applies API key authentication and rate limiting
    to all requests reaching the MCP server mount point.

    This is needed because the MCP ASGI app is mounted separately from
    FastAPI and therefore does not participate in FastAPI's dependency system.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive)
        api_key = request.headers.get("X-API-Key")

        if not api_key or api_key != settings.api_key:
            logger.warning("MCP: rejected request — invalid or missing API key")
            response = JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key", "code": "UNAUTHORIZED"},
            )
            await response(scope, receive, send)
            return

        if not _rate_limiter.is_allowed(api_key):
            logger.warning("MCP: rejected request — rate limit exceeded")
            response = JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "code": "RATE_LIMITED"},
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)
