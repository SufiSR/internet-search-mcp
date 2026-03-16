# Cursor Prompt — Self-Hosted AI Browsing MCP Stack

You are a **senior DevOps and backend engineer**.

Your task is to build a **self-hosted AI browsing backend** that exposes web search and content retrieval through an **MCP-compatible HTTP service**. The system must run entirely in **Docker Compose** and be production-ready for integration with **LibreChat, n8n, and other MCP-capable agents**.

The architecture must allow an LLM to **select between multiple browsing tools** depending on the situation.

---

# Technology Stack

The system must include:

* **SearXNG** → web search aggregation
* **BM25 ranking** → ranking search results
* **Fast HTML fetch extraction** → primary page retrieval
* **Firecrawl fallback** → advanced scraping for difficult pages
* **Python MCP-compatible API service**
* **Docker Compose deployment**

---

# Constraints

* **No Playwright yet**, but architecture must support adding it later.
* **API key authentication is mandatory** for every request.
* Must run on a **single Linux server**.
* Recommended hardware: **4–8 CPU / 8–16 GB RAM**.
* All services must run in **separate containers**.
* No paid APIs.

The system acts as an **AI browsing gateway**.

---

# System Overview

The MCP server must expose **four tools** so that the LLM can decide how to interact with the web.

```
search(query)
fetch(url)
crawl(url)
browse(query)
```

### Tool Responsibilities

| Tool   | Purpose                                                    |
| ------ | ---------------------------------------------------------- |
| search | retrieve search results only                               |
| fetch  | fast extraction for most websites                          |
| crawl  | heavy scraping using Firecrawl                             |
| browse | automatic pipeline combining search + ranking + extraction |

---

# Expected Agent Workflow

Typical LLM usage patterns:

### Case 1 — exploratory search

```
search(query)
```

### Case 2 — direct page retrieval

```
fetch(url)
```

### Case 3 — difficult site

```
crawl(url)
```

### Case 4 — automatic browsing

```
browse(query)
```

Pipeline of `browse`:

```
query
↓
SearXNG search
↓
collect 10 results
↓
BM25 ranking
↓
select top 3 URLs
↓
fast fetch extraction
↓
fallback to Firecrawl if necessary
```

---

# Project Structure

Create this repository:

```
ai-browsing-stack/

docker-compose.yml
.env.example

searxng/
  settings.yml

mcp-server/
  Dockerfile
  requirements.txt

  server.py
  auth.py
  search.py
  ranking.py
  fetch.py
  scrape.py
  tools.py

README.md
```

The code must be **modular and production-ready**.

---

# Docker Compose

Create `docker-compose.yml` with services:

* `searxng`
* `firecrawl`
* `browsing-mcp`

All containers must share a Docker network.

### Exposed Ports

```
SearXNG → 8888
Firecrawl → 3002
MCP API → 8081
```

The compose file must:

* mount SearXNG configuration
* load environment variables
* restart containers automatically
* include **commented placeholders for a future Playwright renderer**

---

# Environment Variables

Create `.env.example`.

```
API_KEY=change_this_to_secure_key

SEARXNG_URL=http://searxng:8080
FIRECRAWL_URL=http://firecrawl:3002

RESULT_COUNT=10
SCRAPE_COUNT=3

RATE_LIMIT_PER_MINUTE=30
```

All services must read configuration from environment variables.

---

# API Security

Every request must require an API key.

Authentication header:

```
X-API-Key: <key>
```

Invalid or missing keys must return:

```
HTTP 401 Unauthorized
```

Authentication logic must be implemented in:

```
auth.py
```

Use a FastAPI dependency:

```
verify_api_key()
```

All endpoints must require this dependency.

---

# Rate Limiting

Implement lightweight in-memory rate limiting per API key.

```
RATE_LIMIT_PER_MINUTE
```

If exceeded:

```
HTTP 429 Too Many Requests
```

Document how **Redis could replace the limiter** later.

---

# SearXNG Configuration

Create minimal `settings.yml`.

Requirements:

* enable JSON API
* include engines:

```
duckduckgo
brave
bing
```

Disable unnecessary features.

API endpoint used:

```
/search?q=query&format=json
```

The MCP service must collect **top 10 results**.

---

# BM25 Ranking

Use Python library:

```
rank_bm25
```

Ranking input must combine:

```
title
snippet content
```

Tokenization method:

```
whitespace splitting
```

Select the **top 3 URLs**.

Implementation file:

```
ranking.py
```

---

# Fast Fetch Extraction (Primary Method)

Implemented in:

```
fetch.py
```

Steps:

1. download page using `requests`
2. extract readable content using `readability-lxml`
3. convert HTML → markdown using `markdownify`

Libraries required:

```
requests
readability-lxml
beautifulsoup4
markdownify
```

If extracted markdown length:

```
< 500 characters
```

Return `None`.

This triggers Firecrawl fallback.

---

# Firecrawl Fallback

If fast extraction fails:

Call Firecrawl.

Endpoint:

```
POST /v1/scrape
```

Request:

```
{
  "url": "...",
  "formats": ["markdown"]
}
```

Return markdown content.

Implementation file:

```
scrape.py
```

---

# MCP Tools

Expose the following endpoints:

```
POST /search
POST /fetch
POST /crawl
POST /browse
```

All endpoints require API authentication.

---

# Search Tool

Input

```
{
 "query": "string"
}
```

Output

```
{
 "results": [
   {
     "title": "...",
     "url": "...",
     "snippet": "..."
   }
 ]
}
```

---

# Fetch Tool

Input

```
{
 "url": "..."
}
```

Return extracted markdown using fast fetch.

---

# Crawl Tool

Input

```
{
 "url": "..."
}
```

Use Firecrawl extraction.

---

# Browse Tool

Input

```
{
 "query": "..."
}
```

Pipeline

```
search
→ BM25 ranking
→ fetch pages
→ fallback to crawl if needed
```

Return structured results.

---

# Playwright Placeholder

Add placeholder function:

```
render_with_browser(url)
```

Return `None`.

Document where Playwright would integrate.

Future pipeline:

```
fetch fails
→ Firecrawl fails
→ Playwright rendering
```

Do **not implement browser yet**.

---

# LibreChat MCP Integration

Example configuration:

```
{
 "mcpServers": {
   "browser": {
     "url": "http://server:8081",
     "headers": {
       "X-API-Key": "your_key"
     }
   }
 }
}
```

Available tools:

```
search
fetch
crawl
browse
```

---

# README

Generate a complete README explaining:

* architecture
* component responsibilities
* installation
* environment configuration
* API authentication
* testing with curl
* LibreChat integration
* future Playwright extension

Include **ASCII architecture diagrams**.

---

# Resource Requirements

Recommended server:

```
4 CPU
8 GB RAM
60 GB SSD
```

Likely Baseline memory usage:

```
≈ 3 GB
```

---

# Code Quality Requirements

* modular Python code
* structured logging
* clean error handling
* environment-based configuration
* secure defaults
* no hardcoded secrets

---

# Deliverable

Generate the **complete repository with all files and contents exactly as they should exist**.

Do not summarize.
