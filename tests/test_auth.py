"""
Tests for authentication and rate limiting.

Uses FastAPI's TestClient via httpx to make requests against the full app,
which exercises both the dependency injection path and the middleware path.
"""

import pytest
from fastapi.testclient import TestClient

from server import app

client = TestClient(app, raise_server_exceptions=False)

VALID_KEY = "test-api-key-fixture"
INVALID_KEY = "wrong-key"


class TestApiKeyAuthentication:
    def test_missing_key_returns_401(self):
        response = client.post("/search", json={"query": "test"})
        assert response.status_code == 401
        # FastAPI wraps HTTPException detail under {"detail": ...}
        assert response.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_invalid_key_returns_401(self):
        response = client.post(
            "/search",
            json={"query": "test"},
            headers={"X-API-Key": INVALID_KEY},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_health_endpoint_requires_no_auth(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_valid_key_is_accepted(self, respx_mock):
        """A valid key should pass auth (SearXNG call is mocked to return empty)."""
        import respx
        import httpx

        with respx.mock:
            respx.get("http://searxng-mock:8080/search").mock(
                return_value=httpx.Response(200, json={"results": []})
            )
            response = client.post(
                "/search",
                json={"query": "test"},
                headers={"X-API-Key": VALID_KEY},
            )

        assert response.status_code == 200


class TestRateLimiter:
    def test_rate_limit_exceeded_returns_429(self):
        """
        Exhaust the rate limit and verify the 429 response.

        Note: the rate limiter uses a shared in-memory state. This test
        temporarily patches the limit to 1 to avoid running 30 requests.
        """
        import auth

        original_limit = auth._rate_limiter._limit
        auth._rate_limiter._limit = 1
        auth._rate_limiter._windows.clear()

        try:
            import respx
            import httpx

            with respx.mock:
                respx.get("http://searxng-mock:8080/search").mock(
                    return_value=httpx.Response(200, json={"results": []})
                )
                # First request should pass
                r1 = client.post(
                    "/search",
                    json={"query": "test"},
                    headers={"X-API-Key": VALID_KEY},
                )
                assert r1.status_code == 200

                # Second request should be rate-limited
                r2 = client.post(
                    "/search",
                    json={"query": "test"},
                    headers={"X-API-Key": VALID_KEY},
                )
                assert r2.status_code == 429
                assert r2.json()["detail"]["code"] == "RATE_LIMITED"
        finally:
            auth._rate_limiter._limit = original_limit
            auth._rate_limiter._windows.clear()
