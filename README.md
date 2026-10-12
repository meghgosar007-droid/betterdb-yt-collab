<br><div align="center">

<img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-0.120-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/Redis-Upstash%20%7C%20Valkey-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
<img src="https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white" />
<img src="https://img.shields.io/badge/Claude%20Code-MCP%20Ready-8B5CF6?style=for-the-badge" />
<img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />


### *AI Infrastructure Observability — RAG Pipeline Demo*

**"Your AI App's Redis is Broken — And You Don't Know It"**


</div>

---

## The Problem

You ship a RAG pipeline. It uses Redis for semantic caching, agent memory, and rate limiting. Three weeks later:

- A LangChain agent runs overnight — **10,000 HSET commands** on one session key
- Your semantic cache grows to **450 MB** — nobody set TTLs
- Someone hits your LLM rate limiter **10,000+ times in 30 seconds**
- RAG pipeline p95 latency creeps up — **HGETALL is the bottleneck**, invisible in aggregate

You open CloudWatch. You see a spike. **The Redis slowlog is already overwritten** — 128 entries, gone in 0.1 seconds at 1,000 cmd/s.

**BetterDB persists everything. Query it hours later, in plain English, from Claude Code.**

---

## What's in This Repo

A minimal **FastAPI RAG application** that generates real Redis keys so BetterDB has actual data to monitor — no fake seeding, no mock data.

```
betterdb-yt-collab/
├── rag/
│   ├── config.py       ← pydantic-settings + Redis + OpenAI clients
│   ├── pipeline.py     ← ingest, retrieve, semantic cache, rate limit, session
│   └── main.py         ← FastAPI: POST /ingest  POST /query  GET /stats  GET /health
├── docker-compose.yml  ← local Valkey (alternative to Upstash)
├── step-by-step.md     ← full demo walkthrough with all commands
├── .env.example        ← credential template
└── pyproject.toml      ← Python dependencies
```

---

## Redis Key Patterns Generated

| Key Pattern | Written by | TTL | BetterDB Feature |
|---|---|---|---|
| `rag:doc:{sha256}` | `POST /ingest` | **None — the bug** | Feature 2, 5 |
| `semantic_cache:{md5}` | `POST /query` | **None — the bug** | Feature 2 |
| `rate_limit:user_{id}:minute` | `POST /query` | 60s ✓ | Feature 4 |
| `rate_limit:user_{id}:hour` | `POST /query` | 3600s ✓ | Feature 4 |
| `langchain:memory:session:{id}` | `POST /query` | **None — the bug** | Feature 3 |

---

## Quick Start

### 1. Install dependencies

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install fastapi uvicorn pypdf numpy pydantic-settings python-multipart openai redis python-dotenv
```

### 2. Configure .env

```bash
cp .env.example .env
# Fill in: OPENAI_API_KEY, REDIS_URL, BETTERDB_TOKEN
```

**Option A — Upstash Redis (cloud, zero infra):**
```dotenv
REDIS_URL=rediss://default:YOUR_TOKEN@quiet-flea-79665.upstash.io:6379
```

**Option B — Local Valkey (Docker, better for slowlog demo):**
```dotenv
REDIS_URL=redis://localhost:6379
```
```bash
docker-compose up -d   # start Valkey
docker-compose ps      # health check
```

### 3. Connect Redis to BetterDB cloud

BetterDB → Manage Connections → + Add Connection → Via Agent → copy token.

**Upstash:**
```bash
docker run -d --name betterdb-agent \
  -e VALKEY_HOST=quiet-flea-79665.upstash.io \
  -e VALKEY_PORT=6379 \
  -e VALKEY_TLS=true \
  -e VALKEY_USERNAME=default \
  -e VALKEY_PASSWORD=YOUR_UPSTASH_TOKEN \
  -e BETTERDB_CLOUD_URL=wss://betterdb-test1.app.betterdb.com/agent/ws \
  -e BETTERDB_TOKEN=YOUR_BETTERDB_AGENT_TOKEN \
  betterdb/agent:latest
```

**Local Valkey:**
```bash
docker run -d --name betterdb-agent-local \
  -e VALKEY_HOST=host.docker.internal \
  -e VALKEY_PORT=6379 \
  -e BETTERDB_CLOUD_URL=wss://betterdb-test1.app.betterdb.com/agent/ws \
  -e BETTERDB_TOKEN=YOUR_BETTERDB_AGENT_TOKEN \
  betterdb/agent:latest
```

### 4. Start FastAPI

```bash
uvicorn rag.main:app --reload --port 8000
```

### 5. Ingest a PDF

```bash
curl -F "file=@BetterDB_YouTube_Proposal.pdf" \
     -H "X-User-ID: demo" \
     http://localhost:8000/ingest
```

### 6. Query

```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -H "X-User-ID: demo" \
     -d '{"query": "What is BetterDB?", "session_id": "default"}'
```

---

## 5 BetterDB Features Demonstrated

### Feature 1 — MCP Server: Debug in Plain English

Ask Claude Code questions — BetterDB answers from real Redis data:

```
"What are the slowest commands in the last 24h?"
"Show me memory breakdown by namespace"
"Who are the top clients by command count?"
"Show me any anomalies detected"
```

### Feature 2 — Semantic Cache TTL Bug

After `/ingest` + `/query`:
- `rag:doc:*` — 21 keys, ~31 KB each, **w/TTL = 0**
- `semantic:cache:*` — 1+ keys, ~31 KB each, **w/TTL = 0**

Memory grows unbounded. No CloudWatch alert fires.

**Fix:** `r.expire(cache_key, 604800)` — 7 days TTL.

### Feature 3 — Agent Memory Runaway

Run multiple queries with the same `session_id`:
- Key count stays **1** (one HASH key)
- Memory grows per query: 850B → 2KB → 4KB → ...
- **w/TTL = 0** — grows forever

### Feature 4 — Rate Limiter Burst Detection

Fire 20 parallel requests — queries 11–20 return `HTTP 429`:

```bash
curl ... &
curl ... &
# × 20
wait && echo "done"
```

See full burst command in [step-by-step.md](step-by-step.md) Section 6.

### Feature 5 — HGETALL Latency Attribution

```
Per-key HGETALL (Upstash):     avg=264ms   p95=272ms
Full scan 21 keys (Upstash):   ~6000ms     ← Redis is the bottleneck
Full scan 21 keys (local):     ~5ms        ← 1200× faster
```

**Fix:** Pipeline all HGETALLs into one round-trip: `~6000ms → ~300ms`.

---

## Full Walkthrough

See **[step-by-step.md](step-by-step.md)** for:
- All curl commands
- All Claude Code MCP questions
- Both Upstash and local Valkey setup
- Troubleshooting guide
- Before/after fix comparisons

---

## Stack

| Component | Choice |
|---|---|
| API | FastAPI 0.120 |
| LLM | OpenAI gpt-4o-mini |
| Embeddings | text-embedding-3-small |
| Redis (cloud) | Upstash Redis |
| Redis (local) | Valkey 8.1 (Docker) |
| Observability | BetterDB cloud + agent |
| MCP | BetterDB MCP → Claude Code |
| Package manager | uv |

---

## License

MIT — free to use, modify, distribute.

---

<div align="center">

**Built by [Krish Naik](https://github.com/krishnaik06) in collaboration with [BetterDB](https://betterdb.com)**

[🌐 betterdb.com](https://betterdb.com) · [📺 Krish Naik Academy](https://www.youtube.com/@krishnaik06)

</div>
