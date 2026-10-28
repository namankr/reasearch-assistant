# Project Brief — Agentic AI Research & Travel Assistant

_Sources: `CLAUDE.md`, `README.md`, `travel_agent_phases_6_to_9.docx`, and the code. Decisions live in [`decision.md`](decision.md)._

## 1. Purpose
A production-grade, multi-phase agentic AI system on Google Gemini. Phases 1–5 built a research assistant
(ReAct loop, memory, caching, routing, evals). Phases 6–9 reuse that stack under `project_id="travel_agent"`
as a three-agent travel planner with calendar conflict detection and human-in-the-loop approval.

## 2. Status
| Phase | Scope | Status |
|---|---|---|
| 1 | ReAct loop + web search | Done |
| 2 | ChromaDB memory, chunking, sliding window, injection sanitiser | Done |
| 3 | L1 LRU + L2 Redis semantic cache | Done |
| 4 | LLM complexity router + SQLite cost tracker | Done |
| 5 | Langfuse tracing, LLM judge, hallucination check, 10 benchmarks, CI runner | Done |
| 6 | Agent A — Researcher (flights/hotels/attractions, Pydantic output) | Code done; needs live API keys to run end to end |
| 7 | Agent B — Coordinator + Google Calendar | Code done; calendar needs OAuth credentials |
| 8 | Agent C — Booker + approval state machine | Code done; booking itself is **simulated** |
| 9 | Parallel research, travel evals, hardening | Code done (see "Remaining gaps") |

## 3. Architecture
```
User ─► travel_pipeline.handle_user_message
         ├─ session status == awaiting_approval? ─► booker.handle_approval (confirm/cancel/edit)
         │                                          (agents never see these messages)
         └─ else ─► Agent B coordinator
                     1. parse intent (Gemini JSON: origin, destination, dates)
                     2. Google Calendar conflict check  ── conflict ─► return report, stop
                     3. Agent A research
                          parallel (asyncio: flights ‖ hotels ‖ attractions, cached) → structure via LLM
                          fallback / revisions: sequential ReAct researcher with tools
                     4. ─► Agent C booker: itinerary → status=awaiting_approval
```
Reused from Phases 1–5: `ChatService` (extended with session state), `CacheManager`, `ModelRouter`,
`VectorMemory`, Langfuse tracer, sanitiser, eval runner pattern.

## 4. Key files (Phases 6–9)
| File | Role |
|---|---|
| `schemas/travel.py` | `FlightOption`, `HotelOption`, `ResearchResult`, `TravelIntent`, `CoordinatorPlan` |
| `tools/{flight,hotel}_search.py`, `tools/attractions.py` | SerpAPI flights/hotels; attractions via configured web search |
| `agent/researcher.py` | Agent A (sequential ReAct, tool-calling) |
| `agent/researcher_async.py` | Agent A parallel + cached variant |
| `agent/coordinator.py` | Agent B |
| `integrations/calendar_client.py` | Google Calendar wrapper + tool definition |
| `agent/booker.py` | Agent C + approval handler |
| `agent/travel_pipeline.py` | Orchestration + approval gate; used by `main_travel.py` |
| `chat/service.py` | `sessions` table: `get/set_status`, `get/set_context`, `delete_sessions_older_than` |
| `evals/travel_benchmarks.py`, `evals/travel_runner.py` | 10 travel benchmarks + CI runner |
| `maintenance.py`, `health.py` | Session cleanup; dependency health check (+ optional FastAPI `/health`) |
| `tests/` | Offline pytest suite (no network/API keys) |

## 5. Run
```bash
pip install -r requirements.txt
python main_travel.py          # travel planner
python -m evals.travel_runner  # live travel evals (needs keys)
python maintenance.py          # delete sessions older than 7 days
pytest tests                   # offline tests
```
Env: `GEMINI_API_KEY`, `SERPAPI_KEY`, `GOOGLE_CALENDAR_CREDENTIALS`, `GOOGLE_CALENDAR_ID` (see `.env.example`).

## 6. Remaining gaps / next steps
- Not run live end to end (no keys in this session): run `python main_travel.py` and `evals.travel_runner` once.
- Real booking APIs (confirm is simulated); per-agent cost breakdown in `CostTracker`.
- Secrets manager migration (AWS SSM / GCP Secret Manager) before sharing.
- Phase 1–5 tests: only the sanitiser is covered; router/cache/memory/evals remain untested.
- Config oddities to confirm: `GEMINI_PRO_MODEL` equals flash-lite and `ENABLE_ROUTER=False` in `config.py`.
- Google OAuth token file must be created out of band (`Credentials.from_authorized_user_file`).
