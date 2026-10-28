# Research Agent — Agentic AI Project

## What this project is
A production-grade, multi-phase agentic AI research assistant built on Google Gemini.
ReAct agent loop + persistent vector memory + two-layer caching + intelligent model
routing + prompt injection defense. See `README.md` for setup/usage and `docs.html`
for the full engineering deep-dive (architecture, FAQ, L3 interview Q&A). 

## Future Enhancements
- Phases 6–9 (multi-agent travel planner) are implemented in code; see `project_brief.md` and `decision.md`.
- Remaining: live end-to-end run with API keys, real booking APIs, per-agent cost tracking, secrets manager.
 
## Phases completed
- Phase 1: ReAct loop + web search tool (DuckDuckGo default via `ddgs`, Tavily optional)
- Phase 2: ChromaDB vector memory + chunking (400 words, 20% overlap) + sliding-window
  context + prompt injection sanitiser
- Phase 3: Two-layer cache — L1 in-memory LRU (`OrderedDict`) + L2 Redis semantic cache
  (cosine similarity, threshold 0.85)
- Phase 4: Model router — LLM complexity classifier (Gemini or Groq, toggle via
  `CLASSIFIER_PROVIDER`) routes simple/moderate → Flash Lite, complex → Pro; SQLite
  cost tracker logs every call
- Phase 5: Langfuse tracing (`observability/tracer.py`, `@observe` decorator + `create_event`),
  LLM-as-judge eval (`evals/judge.py`), hallucination detection (`evals/hallucination.py`),
  10-benchmark suite (`evals/benchmark.py`), CI eval runner with SQLite sink (`evals/runner.py`).
  SDK fixed from Langfuse v2 style to v4 API (OTel-based, `@observe` + `update_current_span`).

## Key architecture decisions
- ChatService is plug-and-play: `project_id` namespaces all sessions in SQLite
- **Request order in `main.py` is Cache → Router → Agent**: check the cache first,
  and only pay for a router classification call on a cache miss. (Previously the
  router ran before the cache check, which meant every cache hit still paid for a
  classification call — fixed 2026-07-03.)
- Cache key is query-only (`query.strip().lower()`), decoupled from the routed model,
  so a non-deterministic classifier decision can't fragment the cache
- Error responses must never be stored in cache (`ERROR_MARKERS` guard in `main.py`)
- `clean_result` (sanitised) is fed to Gemini and vector memory, never the raw tool result
- `_send_with_retry` in `agent/react_agent.py` is a module-level `tenacity`-wrapped
  function (not redefined per call)
- Classifier backend defaults to **Gemini** (`CLASSIFIER_PROVIDER` default is `"gemini"`
  in `config.py`, and no override is set in `.env`); Groq is wired up and available via
  `router.classifier.set_classifier_provider("groq")` but is not the active default

## Project structure
```
├── agent/
│   ├── react_agent.py       # ReAct loop, tenacity retry, tool dispatch
│   └── prompts.py           # System prompt
├── cache/
│   ├── cache_manager.py     # L1 + L2 orchestrator
│   ├── memory_cache.py      # L1 LRU OrderedDict
│   └── redis_cache.py       # L2 Redis semantic cache
├── chat/service.py          # Stateful sessions, SQLite, sliding window
├── memory/
│   ├── vector_store.py      # ChromaDB RAG memory
│   └── chunker.py           # 400-word overlapping chunks
├── router/
│   ├── model_router.py      # Routes simple/moderate→Flash, complex→Pro
│   ├── classifier.py        # Gemini/Groq complexity classifier (togglable)
│   └── cost_tracker.py      # Logs cost per query to SQLite
├── llm/groq_client.py       # Groq chat-completions wrapper (used by classifier)
├── security/sanitiser.py    # Prompt injection regex guard (12 patterns)
├── tools/web_search.py      # DuckDuckGo (default) / Tavily search tool
├── evals/
│   ├── benchmark.py         # 10 curated benchmarks (factual/comparison/security)
│   ├── judge.py             # LLM-as-judge via Gemini (accuracy/completeness/hallucination)
│   ├── hallucination.py     # Per-claim cosine grounding check vs ChromaDB memory
│   └── runner.py            # Eval loop, SQLite sink, CI exit code
├── observability/
│   └── tracer.py            # Langfuse @observe + create_event (v4 OTel-based SDK)
├── config.py                # All settings, API keys
├── main.py                  # Entry point, wires everything together
├── README.md                # Setup + usage + architecture summary
└── docs.html                # Full engineering docs, FAQ, interview Q&A
```

## Known issues / gaps
- Test suite is minimal: `tests/` (offline, `pytest tests`) covers Phases 6–9 and the sanitiser only;
  Phases 1–5 (router, cache, memory, evals) remain untested.
- Gemini free tier hits 429 daily limit quickly — retry/back-off (`tenacity`) and an
  optional Groq classifier exist as mitigations, but the classifier defaults to Gemini
  (see above). Cache hits now skip the classifier entirely (cache runs before router),
  so quota pressure only comes from actual cache misses.
- `time.sleep(1)` after every ReAct iteration to throttle the free tier
- Redis must be running for L2 cache: `docker run -d -p 6379:6379 redis` (L2 fails
  open/disabled if Redis is unreachable — does not crash the agent)
- Model IDs in `config.py` (`gemini-3.1-flash-lite`, `gemini-3.1-pro`) differ from
  `LLM_MODEL` (`gemini-2.5-flash`, used only as a fallback default) — worth confirming
  these are the intended production model names before Phase 5 eval work locks them in

## Tech stack
- LLM: Gemini (router picks per-query between a Flash-tier and Pro-tier model defined
  in `config.py`; `LLM_MODEL` is a separate unrouted fallback)
- Classifier: Gemini (default) or Groq Llama 3.3 70B (togglable, no daily limit)
- Vector DB: ChromaDB (local, persistent)
- Cache: Python `OrderedDict` (L1) + Redis (L2, semantic)
- Embeddings: sentence-transformers `all-MiniLM-L6-v2`
- State: SQLite via `ChatService` (chat history) + `CostTracker` (cost log)
- Search: DuckDuckGo (`ddgs`, default, no key) or Tavily (optional, `TAVILY_API_KEY`)
- Tracing/evals: Langfuse v4 (`@observe` decorator, `create_event`); eval suite with LLM judge + hallucination detection

## Docs maintenance
- `README.md` is the source of truth for setup/usage/architecture — re-read it when
  phases change and reconcile this file against it.
- `docs.html` is the source of truth for deep architectural rationale (FAQ) and
  interview-style Q&A — useful context for *why* a decision was made, not just *what*.

## Code Review and Approvals

- code review is done by senior L3 level engineers and cursor
