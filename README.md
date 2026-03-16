# AI Browsing MCP Stack

A self-hosted web browsing backend that gives AI agents the ability to search
the web, retrieve pages, and scrape difficult sites — exposed through both a
**REST API** and a native **MCP server** (JSON-RPC 2.0 + SSE).

Compatible with **LibreChat**, **n8n**, and any MCP-capable agent framework.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Clients                                  │
│   LibreChat (MCP/SSE)     n8n (MCP or REST)     curl (REST)        │
└────────────┬──────────────────────┬──────────────────┬─────────────┘
             │  X-API-Key header    │                  │
             ▼                      ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    browsing-mcp  :8081                              │
│                                                                     │
│   POST /mcp (JSON-RPC 2.0)      GET /mcp (SSE stream)              │
│   POST /search   POST /fetch   POST /crawl   POST /browse          │
│   GET  /health                                                      │
│                                                                     │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│   │search.py │  │ranking.py│  │ fetch.py │  │   tools.py       │  │
│   │SearXNG   │  │  BM25    │  │readabilty│  │browse pipeline   │  │
│   │  client  │  │  ranker  │  │markdownfy│  │asyncio.gather    │  │
│   └────┬─────┘  └──────────┘  └──────────┘  └──────────────────┘  │
│        │                                              │             │
└────────┼──────────────────────────────────────────────┼─────────────┘
         │                                              │
         ▼                                              ▼
┌────────────────┐              ┌───────────────────────────────────┐
│ searxng  :8888 │              │        Firecrawl stack            │
│                │              │  firecrawl-api      :3002         │
│  duckduckgo    │              │  firecrawl-worker   (internal)    │
│  brave         │              │  playwright-service (internal)    │
│  bing          │              └───────────────────────────────────┘
└────────────────┘
         │                                              │
         └──────────────────┬───────────────────────────┘
                            ▼
                   ┌────────────────┐
                   │  redis  (shared)│
                   │  SearXNG limiter│
                   │  Firecrawl queue│
                   └────────────────┘
```

---

## Component Responsibilities

| Component | Role |
|---|---|
| **SearXNG** | Aggregates results from DuckDuckGo, Brave, and Bing. Provides a JSON API. |
| **Redis** | Shared infrastructure for SearXNG's rate limiter and Firecrawl's job queue. |
| **Firecrawl API** | Accepts scraping requests and enqueues them for workers. |
| **Firecrawl Worker** | Processes scraping jobs using the Playwright service. |
| **Playwright Service** | Headless browser runtime (Firecrawl internal dependency). |
| **browsing-mcp** | Our service: REST API + MCP server. Orchestrates all tools. |

---

## Tools

| Tool | Endpoint | Purpose |
|---|---|---|
| `search` | `POST /search` | Return search results (title, url, snippet) without fetching pages |
| `fetch` | `POST /fetch` | Fast page retrieval using readability extraction |
| `crawl` | `POST /crawl` | Heavy scraping via Firecrawl for difficult pages |
| `browse` | `POST /browse` | Automatic pipeline: search → BM25 rank → concurrent fetch with fallback |

### Browse pipeline

```
query
  │
  ▼
search_web()          ← SearXNG, collect 10 results
  │
  ▼
rank_results()        ← BM25 re-ranking, select top 3
  │
  ▼
asyncio.gather()      ← fetch all 3 URLs concurrently
  │
  ├── fetch_page()    ← fast extraction (readability + markdownify)
  │       │ fails?
  │       ▼
  └── scrape_page()   ← Firecrawl fallback
          │ fails?
          ▼
      source: "unavailable"
```

---

## Prerequisites

- Docker and Docker Compose v2
- A Linux server (single host)
- Recommended hardware: **4 CPU / 8 GB RAM / 60 GB SSD**
- Estimated baseline memory: ~3 GB

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/your-org/ai-browsing-stack.git
cd ai-browsing-stack
```

**2. Create your environment file**

```bash
cp .env.example .env
```

Edit `.env` and set a strong `API_KEY`:

```bash
# Generate a secure key
openssl rand -hex 32
```

Also update the `secret_key` in `searxng/settings.yml` for production.

**3. Start the stack**

```bash
docker compose up -d
```

**4. Verify services are healthy**

```bash
docker compose ps
```

All services should show `healthy` status. Allow ~60 seconds on first run for
Firecrawl to initialise.

**5. Check the MCP service**

```bash
curl http://localhost:8081/health
# {"status":"ok","service":"browsing-mcp"}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(required)* | Authentication key for all API requests |
| `SEARXNG_URL` | `http://searxng:8080` | Internal SearXNG address |
| `FIRECRAWL_URL` | `http://firecrawl-api:3002` | Internal Firecrawl address |
| `RESULT_COUNT` | `10` | Number of search results to retrieve |
| `SCRAPE_COUNT` | `3` | Number of top URLs to fetch in browse pipeline |
| `MAX_CONTENT_LENGTH` | `50000` | Maximum characters returned per page |
| `RATE_LIMIT_PER_MINUTE` | `30` | Max requests per API key per minute |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## API Authentication

All endpoints (except `/health`) require the `X-API-Key` header:

```
X-API-Key: your_api_key_here
```

**Missing or invalid key:**
```json
HTTP 401
{"error": "Invalid or missing API key", "code": "UNAUTHORIZED"}
```

**Rate limit exceeded:**
```json
HTTP 429
{"error": "Rate limit exceeded", "code": "RATE_LIMITED"}
```

> **Multi-worker note:** The rate limiter is in-memory and only correct for a
> single Uvicorn worker (the default). For scaling, replace it with a
> Redis-backed implementation using sorted sets.

---

## Testing with curl

Set your key in the shell first:

```bash
export KEY="your_api_key_here"
export HOST="http://localhost:8081"
```

**Search**

```bash
curl -s -X POST "$HOST/search" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "python asyncio tutorial"}' | jq .
```

**Fetch**

```bash
curl -s -X POST "$HOST/fetch" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org/3/library/asyncio.html"}' | jq .content
```

**Crawl** (Firecrawl fallback)

```bash
curl -s -X POST "$HOST/crawl" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/js-heavy-page"}' | jq .content
```

**Browse** (full automatic pipeline)

```bash
curl -s -X POST "$HOST/browse" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "best practices for Docker Compose healthchecks"}' | jq .
```

---

## LibreChat Integration

In your LibreChat configuration file, add the MCP server under `mcpServers`:

```json
{
  "mcpServers": {
    "browser": {
      "url": "http://your-server-ip:8081/mcp",
      "headers": {
        "X-API-Key": "your_api_key_here"
      }
    }
  }
}
```

LibreChat connects via the SSE transport (`GET /mcp`). The four tools —
`search`, `fetch`, `crawl`, and `browse` — become available to the LLM
automatically after the MCP handshake.

---

## n8n Integration

**Option A — MCP node (if available)**

Point the MCP node at `http://your-server-ip:8081/mcp` with the
`X-API-Key` header.

**Option B — HTTP Request nodes**

Use standard HTTP Request nodes pointed at the REST endpoints
(`/search`, `/fetch`, `/crawl`, `/browse`) with the `X-API-Key` header set.

---

## Running Tests

Install dependencies locally (or run inside the container):

```bash
cd mcp-server
pip install -r requirements.txt
pytest ../tests/ -v
```

Tests use `respx` to mock all external HTTP calls — no running services required.

---

## Extending the Stack

### Adding a Playwright Browser Renderer

The stack has a documented integration point for a dedicated browser rendering
service. When you are ready to implement it:

1. **Implement `render_with_browser()` in `mcp-server/fetch.py`**

   Replace the current stub with an `httpx` call to your renderer service.
   The rendered HTML should then be passed through `_extract_markdown()`.

2. **Add the renderer service to `docker-compose.yml`**

   An example placeholder comment is already present in the compose file
   (`playwright-renderer` service block).

3. **Extend the fallback chain in `tools.py`**

   ```python
   # Current chain:
   fetch_page → scrape_page → unavailable

   # Extended chain:
   fetch_page → scrape_page → render_with_browser → unavailable
   ```

4. **Add a `PLAYWRIGHT_RENDERER_URL` env var** to `config.py` and `.env.example`.

> **Note on Playwright MCP:** Microsoft's `@playwright/mcp` server is a
> separate, more powerful capability — it gives the LLM *interactive* browser
> control (clicking, form filling, navigation). This is distinct from the
> content extraction renderer described above and could be added as a fifth
> tool in a future iteration.

---

## Project Structure

```
ai-browsing-stack/
├── docker-compose.yml       Infrastructure definition (6 services)
├── .env.example             Environment variable template
├── .gitignore
├── pyproject.toml           black + ruff configuration
├── README.md
├── searxng/
│   └── settings.yml         SearXNG configuration
├── mcp-server/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py            Pydantic Settings (single source of truth)
│   ├── auth.py              API key auth + rate limiter + ASGI middleware
│   ├── search.py            SearXNG async client
│   ├── ranking.py           BM25 result re-ranking (pure function)
│   ├── fetch.py             Fast HTML fetch + readability + markdownify
│   ├── scrape.py            Firecrawl async client
│   ├── tools.py             Browse pipeline (asyncio.gather)
│   ├── mcp_handler.py       MCP tool registration (FastMCP SDK)
│   └── server.py            FastAPI app + REST routes + MCP mount
└── tests/
    ├── conftest.py          Shared fixtures
    ├── test_auth.py
    ├── test_ranking.py
    ├── test_fetch.py
    └── test_tools.py
```
