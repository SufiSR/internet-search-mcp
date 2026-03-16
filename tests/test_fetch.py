"""
Tests for fast fetch content extraction.

httpx calls are intercepted by respx. No real network requests are made.
"""

import httpx
import pytest
import respx

from fetch import MIN_CONTENT_LENGTH, fetch_page


SAMPLE_URL = "https://example.com/article"

# Minimal HTML that readability-lxml can extract substantial content from
READABLE_HTML = """
<html>
<head><title>Test Article</title></head>
<body>
  <article>
    <h1>How asyncio works in Python</h1>
    <p>
      asyncio is a library to write concurrent code using the async and await syntax.
      It is used as a foundation for multiple Python asynchronous frameworks that
      provide high-performance network and web servers, database connection libraries,
      distributed task queues, and so on.
    </p>
    <p>
      The event loop is the core of every asyncio application. Event loops run
      asynchronous tasks and callbacks, perform network IO operations, and run
      subprocesses. Application developers should typically use the high-level asyncio
      functions, such as asyncio.run(), and should rarely need to reference the loop
      object or call its methods.
    </p>
    <p>
      Coroutines declared with the async/await syntax are the preferred way of writing
      asyncio applications. When a coroutine is paused by an await expression, the
      event loop can run other tasks. This cooperative multitasking makes asyncio
      efficient for I/O-bound workloads.
    </p>
  </article>
</body>
</html>
"""

THIN_HTML = "<html><body><p>Hi</p></body></html>"


class TestFetchPage:
    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_extraction_returns_markdown(self):
        respx.get(SAMPLE_URL).mock(
            return_value=httpx.Response(200, text=READABLE_HTML, headers={"content-type": "text/html"})
        )

        result = await fetch_page(SAMPLE_URL)

        assert result is not None
        assert len(result) >= MIN_CONTENT_LENGTH
        # readability + markdownify should produce heading markers
        assert "#" in result or "asyncio" in result.lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_thin_content_returns_none(self):
        """Content below 500 chars should return None to trigger fallback."""
        respx.get(SAMPLE_URL).mock(
            return_value=httpx.Response(200, text=THIN_HTML, headers={"content-type": "text/html"})
        )

        result = await fetch_page(SAMPLE_URL)

        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_returns_none(self):
        respx.get(SAMPLE_URL).mock(side_effect=httpx.TimeoutException("timed out"))

        result = await fetch_page(SAMPLE_URL)

        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_returns_none(self):
        respx.get(SAMPLE_URL).mock(return_value=httpx.Response(404))

        result = await fetch_page(SAMPLE_URL)

        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_error_returns_none(self):
        respx.get(SAMPLE_URL).mock(side_effect=httpx.ConnectError("refused"))

        result = await fetch_page(SAMPLE_URL)

        assert result is None
