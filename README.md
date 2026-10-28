# Research Assistant Agent

A production-grade, multi-phase AI research assistant built on top of Google Gemini. It combines a ReAct agent loop, persistent memory, two-layer caching, intelligent model routing, and prompt injection defense — all wired together in a clean, modular architecture.

---

## Architecture Overview

```
User Input
    │
    ├─► Security: sanitise input
    │
    ├─► Phase 4 — Router: classify complexity → pick model (Flash / Pro)
    │
    ├─► Phase 3 — Cache check:
    │       L1 (in-memory, exact-match)  ──hit──► return cached answer
    │       L2 (Redis, semantic cosine)  ──hit──► promote to L1 + return
    │
    ├─► Phase 1 — ReAct Agent Loop (up to MAX_ITERATIONS):
    │       Think → Tool call (web_search) → Observe → Repeat → Final answer
    │
    ├─► Phase 2 — Vector Memory:
    │       Retrieve relevant past findings (ChromaDB)
    │       Store tool results as embeddings for future sessions
    │
    └─► Cache store → Cost log → Print response
```

---

## Phases Built

### Phase 1 — ReAct Agent
- Gemini-powered agent with function calling (`web_search`)
- Iterative Think → Act → Observe loop, capped at `MAX_ITERATIONS`
- Supports DuckDuckGo (free) and Tavily as search backends
- Retry with exponential back-off on Gemini 429 rate limits (`tenacity`)

### Phase 2 — Persistent Memory
- **ChromaDB** persistent vector store, one collection per project
- Tool results are chunked (400 words, 20% overlap) and embedded using `sentence-transformers`
- Session-scoped retrieval: past findings from the current session are injected as context before each agent call
- Token-capped context window using `tiktoken` — stays under Gemini's limit

### Phase 3 — Two-Layer Cache
- **L1**: `OrderedDict`-based in-memory exact-match cache (LRU eviction at `L1_MAX_SIZE`)
- **L2**: Redis-backed semantic cache — cosine similarity over `sentence-transformers` embeddings
- Cache key is query-only (decoupled from routing model) to prevent fragmentation
- Error responses are never cached (`ERROR_MARKERS` guard)
- Graceful L2 fallback if Redis is unavailable

### Phase 4 — Model Router
- LLM-based complexity classifier (Gemini Flash or Groq Llama 3.3) labels queries `simple / moderate / complex`
- `ModelRouter` maps complexity to Gemini Flash Lite (cheap) or Gemini Pro (capable)
- `CostTracker` logs every call to SQLite — model, tokens estimate, USD cost, cache hit flag
- Router can be toggled off (`ENABLE_ROUTER=False`) to hard-code Flash

### Phase 5 — Evals & Observability
- **Langfuse tracing** (`observability/tracer.py`): every `run_agent()` call is wrapped with `@observe`, recording inputs, output preview, and latency; individual tool calls logged as Langfuse events
- **LLM-as-judge** (`evals/judge.py`): Gemini scores each answer on accuracy (0–10), completeness (0–10), and hallucination risk (0–10)
- **Hallucination detection** (`evals/hallucination.py`): each sentence in an answer is compared via cosine similarity against the session's ChromaDB memory; claims below `HALLUCINATION_THRESHOLD` are flagged
- **Benchmark suite** (`evals/benchmark.py`): 10 curated queries across factual, comparison, and security categories; each has `expected_keywords` (must appear) and `should_not_contain` (refusal/disclaimer guard)
- **Eval runner** (`evals/runner.py`): runs all benchmarks, saves results to SQLite (`eval_results` table), prints a summary, and exits non-zero when pass rate < `EVAL_PASS_THRESHOLD` — CI-ready

### Security
- Regex-based prompt injection scanner (`sanitiser.py`) applied to all tool results before they reach the LLM
- 12 known attack patterns (jailbreak, DAN mode, role-override, INST tags, etc.)
- Flagged content is redacted in-place — the agent never sees raw injected text

---

## Phases 6–9 — Multi-Agent Travel Planner

Run with `python main_travel.py`. Full detail in [`project_brief.md`](project_brief.md); rationale in [`decision.md`](decision.md).

- **Phase 6 — Agent A (Researcher):** flights/hotels (SerpAPI) + attractions, returned as validated Pydantic `ResearchResult`.
- **Phase 7 — Agent B (Coordinator):** parses dates, checks Google Calendar *before* researching, delegates to Agent A.
- **Phase 8 — Agent C (Booker):** builds the itinerary and pauses at `awaiting_approval`; `confirm` / `cancel` / `edit …` are handled by the service layer (booking is simulated).
- **Phase 9 — Hardening:** parallel + cached research, travel evals (`python -m evals.travel_runner`), tool-output cap, session cleanup (`python maintenance.py`), health check (`health.py`).

Extra env vars: `SERPAPI_KEY`, `GOOGLE_CALENDAR_CREDENTIALS`, `GOOGLE_CALENDAR_ID`. Tests: `pytest tests` (offline).

---

## Project Structure

```
├── main.py                  Entry point — REPL loop wiring all phases
├── config.py                All tuneable constants in one place
├── requirements.txt
│
├── agent/
│   ├── react_agent.py       ReAct loop, Gemini chat, tool dispatch
│   └── prompts.py           System prompt
│
├── cache/
│   ├── cache_manager.py     Orchestrates L1 + L2
│   ├── memory_cache.py      L1 in-memory LRU cache
│   └── redis_cache.py       L2 Redis semantic cache
│
├── chat/
│   └── service.py           SQLite-backed session + history management
│
├── memory/
│   ├── vector_store.py      ChromaDB wrapper — store + retrieve
│   └── chunker.py           Text splitter with overlap
│
├── router/
│   ├── model_router.py      Routing table (complexity → model)
│   ├── classifier.py        LLM complexity classifier (Gemini / Groq)
│   └── cost_tracker.py      SQLite cost log + summary printer
│
├── security/
│   └── sanitiser.py         Prompt injection detection + redaction
│
├── tools/
│   └── web_search.py        DuckDuckGo / Tavily search tool
│
├── evals/
│   ├── benchmark.py         10 curated eval queries with keyword + forbidden checks
│   ├── judge.py             LLM-as-judge (Gemini) — accuracy / completeness / hallucination risk
│   ├── hallucination.py     Per-claim grounding check against ChromaDB session memory
│   └── runner.py            Full eval loop — scores, SQLite sink, CI exit code
│
└── observability/
    └── tracer.py            Langfuse @observe decorator + tool event logger
```

---

## Setup

### 1. Prerequisites
- Python 3.11+
- Docker (for Redis L2 cache)

### 2. Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Environment variables
Create a `.env` file:
```env
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here          # optional — only needed for Groq classifier
TAVILY_API_KEY=your_key_here        # optional — only needed for Tavily search
SEARCH_PROVIDER=ddgs                # ddgs (default) or tavily
CLASSIFIER_PROVIDER=gemini          # gemini (default) or groq

# Phase 5 — Langfuse observability (optional)
LANGFUSE_PUBLIC_KEY=your_key_here
LANGFUSE_SECRET_KEY=your_key_here
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 6. Run evals
```bash
python -m evals.runner
```

### 4. Start Redis (for L2 cache)
```bash
docker run -d --name agent-redis -p 6379:6379 redis
```

### 5. Run
```bash
python main.py
```

### REPL commands
| Command | Effect |
|---|---|
| `quit` | Exit and print cache + cost stats |
| `new` | Start a new session |
| `history` | Print conversation history |
| `stats` | Print cache hits and cost summary |

---

## Key Config (`config.py`)

| Variable | Default | Purpose |
|---|---|---|
| `MAX_ITERATIONS` | 4 | ReAct loop safety cap |
| `ENABLE_ROUTER` | `True` | Route to Pro for complex queries |
| `CACHE_SIMILARITY_THRESHOLD` | 0.85 | L2 cosine hit threshold |
| `L1_MAX_SIZE` | 100 | Max L1 cache entries |
| `REDIS_TTL_SECONDS` | 3600 | L2 entry TTL |
| `MEMORY_TOP_K` | 3 | Chunks retrieved per query |
| `CHUNK_SIZE` | 400 | Words per memory chunk |
| `MAX_CONTEXT_TOKENS` | 8000 | Context window cap |
| `EVAL_PASS_THRESHOLD` | 0.7 | Min benchmark pass rate for CI green |
| `HALLUCINATION_THRESHOLD` | 0.5 | Cosine score below which a claim is flagged |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | — | Langfuse project secret key |
| `LANGFUSE_HOST` | — | Langfuse instance URL |

---

## Dependencies

| Package | Role |
|---|---|
| `google-genai` | Gemini LLM + function calling |
| `groq` | Fallback classifier LLM |
| `chromadb` | Persistent vector memory |
| `sentence-transformers` | Local embeddings (all-MiniLM-L6-v2) |
| `redis` | L2 semantic cache backend |
| `numpy` | Cosine similarity computation |
| `tiktoken` | Token counting for context windows |
| `tenacity` | Retry with exponential back-off |
| `ddgs` | DuckDuckGo search (no API key) |
| `tavily-python` | Tavily search (premium) |
| `truststore` | Windows native SSL cert store |
| `python-dotenv` | `.env` loading |
| `sqlite3` | Chat history + cost log + eval results (stdlib) |
| `langfuse` | LLM observability — traces, spans, events |
| `pytest` | Eval runner test harness |
