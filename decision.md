# Decision Log

Newest at the bottom; add a row whenever a non-obvious choice is made.

| ID | Date | Decision | Rationale / alternatives |
|---|---|---|---|
| D-001 | 2026-07-03 | Request order is Cache → Router → Agent | A cache hit should not pay for a classifier call. (From CLAUDE.md.) |
| D-002 | 2026-07-03 | Cache key is query-only; error responses never cached | Avoid fragmentation from non-deterministic routing; don't cache failures. |
| D-003 | 2026-10-28 | Travel agent is a new `project_id`, not a new codebase | Reuses ChatService/cache/router/memory/tracer per the Phases 6–9 guide. |
| D-004 | 2026-10-28 | Agents B/C live in `agent/` (not `agents/` as in the docx); Calendar wrapper in `integrations/` (not `mcp/`) | `agent/researcher.py` already existed; a local `mcp/` package would shadow the real `mcp` PyPI package. |
| D-005 | 2026-10-28 | Attractions tool reuses `web_search` (provider-agnostic) | Doc said Tavily; default provider is DuckDuckGo, no extra key. Tavily still works via `SEARCH_PROVIDER`. |
| D-006 | 2026-10-28 | Google Calendar client is built lazily and called directly, not via an MCP server process | Importing never needs credentials; no second server. Tool def kept so it can move behind real MCP later. |
| D-007 | 2026-10-28 | Calendar failure/unconfigured **fails open** with an explicit "Calendar not checked" note | Missing creds shouldn't block research and the user is told. Alternative: fail closed (safer, but blocks all use without OAuth). |
| D-008 | 2026-10-28 | Conflict check runs before research; date range inclusive of end date | Validate cheap constraints before expensive work (from the guide). |
| D-009 | 2026-10-28 | Intent (origin/destination/dates) parsed by a JSON-mode Gemini call with today's date injected | Needed for calendar check and parallel tools; `TravelIntent` validates it. |
| D-010 | 2026-10-28 | Approval is a service-layer state machine (`running → awaiting_approval → completed/cancelled`), not prompt logic | Agents never see confirm/cancel; deterministic. |
| D-011 | 2026-10-28 | Fixed the guide's `set_context` (UPDATE on a missing row was a no-op) by creating the session row first; lookups scoped by project | Guide code lost context when `set_context` ran before `set_status`. |
| D-012 | 2026-10-28 | "confirm" **simulates** booking and says so; dropped the guide's "confirmation email" claim | No booking/email integration exists; don't tell users something false. |
| D-013 | 2026-10-28 | Itinerary formatted deterministically (cheapest flight, top-rated hotel), no `Itinerary` schema | No hallucination risk, free, testable. Revisit for day-by-day plans. |
| D-014 | 2026-10-28 | Edits re-run the coordinator with original request + revision and use the sequential ReAct researcher | The parallel path uses only structured intent, so it would ignore "direct flights only" and could return a stale cached result. |
| D-015 | 2026-10-28 | Parallel Agent A runs flights ‖ hotels ‖ attractions, not attractions after flights | Intent already supplies the destination; no dependency on flight results. |
| D-016 | 2026-10-28 | Parallel path: `asyncio.to_thread` + `Semaphore(5)` + per-tool timeout; failed branch degrades to empty; sequential fallback if it fails | Tools are blocking SDK calls; graceful degradation per the hardening checklist. |
| D-017 | 2026-10-28 | Research cached as `travel:origin:dest:start:end` via `CacheManager`, only when flights or hotels exist | Cross-session reuse without caching failures. L2 is semantic and TTL is `REDIS_TTL_SECONDS` (1h) so prices stay fresh. |
| D-018 | 2026-10-28 | Tool output truncated to `MAX_TOOL_OUTPUT_CHARS` (8000) after sanitising | Context-poisoning / token-blowup guard. |
| D-019 | 2026-10-28 | Widened the "ignore … instructions" injection regex to allow stacked qualifiers | "Ignore all previous instructions" bypassed the old pattern; found by a new test. |
| D-020 | 2026-10-28 | Health check is a plain function with an optional FastAPI `app` | Avoids a hard FastAPI dependency; Redis only degrades status because L2 fails open. |
| D-021 | 2026-10-28 | Tests are offline (temp SQLite, fake calendar, patched agents); live evals are a separate runner | Deterministic CI without API keys or quota. |
| D-022 | 2026-10-28 | Benchmark t03 treats ≈ $40/night as ₹3000 | Tools return USD; fixed approximate rate. |
| D-023 | 2026-10-28 | Deferred: per-agent cost breakdown, real booking APIs, secrets manager, tests for Phases 1–5 | Out of scope this pass; listed in `project_brief.md`. |
