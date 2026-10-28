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
| 8 | Agent C — Booker + approval state machine | Code done; confirm creates a real all-day Google Calendar event (no flight/hotel purchase). Test UI: `python ui_server.py --port 8765` |
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
- Real flight/hotel booking APIs (confirm only writes a calendar event); per-agent cost breakdown in `CostTracker`.
- Secrets manager migration (AWS SSM / GCP Secret Manager) before sharing.
- Phase 1–5 tests: only the sanitiser is covered; router/cache/memory/evals remain untested.
- Config oddities to confirm: `GEMINI_PRO_MODEL` equals flash-lite and `ENABLE_ROUTER=False` in `config.py`.
- Google OAuth token file must be created out of band (`Credentials.from_authorized_user_file`); `python google_auth.py` creates it.

---

# 7. Interview Prep

_Sources: `CLAUDE.md`, `README.md`, `concepts.txt`, `agentic_ai_project_reference.html`, the LATAM `interview-prep.html` (RAG Triad), and the Phases 6–9 guide._

## 7.1 30-second pitch
I built an agentic research assistant on Gemini from scratch: a ReAct loop with tool use, ChromaDB RAG memory with a sliding context window, a two-layer semantic cache, an LLM complexity router with cost tracking, a prompt-injection sanitiser, and an eval harness (LLM-as-judge, hallucination check, Langfuse tracing, CI pass threshold). I then extended it into a three-agent travel planner: a researcher with Pydantic-validated output, a coordinator that checks Google Calendar before spending on research, and a booker with a service-layer approval state machine.

Themes: **cost** (cache → router → agent, token windows, output caps) · **reliability** (retries, structured output, graceful degradation) · **safety** (injection redaction, HITL outside the LLM) · **measurability** (benchmarks, judge, grounding, traces, cost log).

## 7.2 ReAct agent & tool use
ReAct = Reason + Act. The model alternates between deciding what it needs and calling a tool; each observation feeds the next step until it answers or hits `MAX_ITERATIONS` (4).
- Native Gemini function calling instead of parsing "Action:" text: structured and less brittle.
- Iteration cap prevents runaway loops and cost.
- Tool result path: raw result → sanitise → truncate → vector memory and back to the model. The model never sees the raw result.
- Retry: module-level `tenacity` wrapper on HTTP 429 only, exponential back-off with jitter.
- Weaknesses: only the first response part is inspected (no parallel function calls); `time.sleep(1)` throttles the free tier.

## 7.3 RAG & memory
**RAG** retrieves relevant text at query time and puts it in the prompt so the model answers from evidence rather than parametric memory. It reduces hallucination, supports fresh/private knowledge, and is cheaper than fine-tuning for knowledge that changes.

| Stage | Implementation | Why |
|---|---|---|
| Ingest | Tool results chunked to 400 words, 20% overlap | Small chunks embed precisely; overlap protects boundary sentences |
| Embed | `all-MiniLM-L6-v2` (384-d, local) | Free, fast, data stays local |
| Store | ChromaDB, collection per `project_id`, `session_id` metadata | Plug-and-play projects; session isolation |
| Retrieve | Top-K (3), filtered to current session | No cross-session bleed |
| Augment | Injected as a prior turn "[Relevant past findings]" | Keeps the system prompt static and cache-friendly |

Context order: system prompt → RAG chunks → sliding window (last 10 turns, tiktoken-counted, warn at 85% of 8000) → current message.

**Be candid:** retrieval is dense-only with fixed top-K, no re-ranking, no hybrid (BM25), and no similarity cut-off, so weak matches still get injected. Chunk size is words in code but "characters" in older docs. These are the first things to improve.

## 7.4 The RAG Triad — evaluating LLM + context
Three relationships among **query**, **retrieved context** and **answer**. Each leg isolates a different failure, so you know where to fix things.

| Leg | Question | Failure it catches | How to measure |
|---|---|---|---|
| **Context relevance** | Is the retrieved context relevant to the query? | Bad chunking, weak embeddings, wrong K → noise or missing evidence | LLM-judge each chunk vs query; or labelled Recall@k / MRR / precision@k |
| **Groundedness** (faithfulness) | Is every claim in the answer supported by the context? | Hallucination: model fills gaps from its own memory | Split answer into claims; verify each against context (NLI / LLM / similarity) |
| **Answer relevance** | Does the answer address the question? | Faithful but off-topic, wrong period/entity | LLM-judge answer vs query; or reverse-generate questions and compare |

**Diagnosis**
| Symptom | Leg | Fix |
|---|---|---|
| Fluent but wrong; context was irrelevant | Context relevance | Better chunking, hybrid search, re-ranker, tune K, metadata filters |
| Right context, answer adds facts not in it | Groundedness | "Answer only from context" prompt, lower temperature, citations, refuse when unsupported |
| Faithful but doesn't answer the question | Answer relevance | Query rewriting, intent handling, output format |

**Mapping to this project**
| Leg | What exists | Gap |
|---|---|---|
| Context relevance | Top-K retrieval from ChromaDB (`MEMORY_TOP_K=3`) | Not scored. Add a judge or labelled retrieval set |
| Groundedness | `evals/hallucination.py` (per-sentence cosine vs session memory, flagged below `HALLUCINATION_THRESHOLD`); judge's `hallucination_risk` | Cosine is a topical proxy, not entailment. Add claim-level NLI/LLM verification |
| Answer relevance | `evals/judge.py` accuracy + completeness; benchmark `expected_keywords` | No explicit relevance score |

**Caveats to say aloud**
- High groundedness ≠ correct: a wrong-but-consistent source gives a faithful, wrong answer. Protect context relevance first.
- The judge LLM should be a different or stronger model than the generator (self-preference bias); calibrate against a small human-labelled set.
- Cosine-based grounding can pass paraphrased false claims and fail valid inferences.
- For tool-backed answers (travel prices) groundedness is deterministic: every number in the itinerary must appear in the tool output.

**Applied to the travel agent:** context relevance = results match parsed destination/dates; groundedness = prices/airlines/ratings exist in tool results (the itinerary is built without an LLM); answer relevance = itinerary matches the request, including edits like "direct flights only".

## 7.5 Evaluation metrics & tools
Two lenses: the **RAG Triad** for the generative side, **classic ML metrics** for parts that act as classifiers or rankers.

| Component | Framed as | Metrics |
|---|---|---|
| Retriever | Ranking | Recall@k, precision@k, MRR, nDCG |
| Travel intent extraction | Field extraction | Per-field P/R/F1, exact match, JSON-validity rate |
| Complexity classifier | Classification | Accuracy, confusion matrix |
| Semantic cache | Binary match | Hit rate, false-positive rate at threshold, PR curve |
| End to end | Task | Pass rate, latency p50/p95, tokens and $ per request |

Precision = TP/(TP+FP); Recall = TP/(TP+FN); F1 = harmonic mean. Prefer per-class metrics on imbalanced data.

Tools: **TruLens** (native triad + dashboard), **Ragas** (faithfulness, answer relevancy, context precision/recall), **DeepEval** (pytest-style, G-Eval), **Langfuse** (used here: traces, scores), **scikit-learn** (P/R/F1, confusion matrix).
Rollout: golden dataset (~100 cases) → retrieval metrics → score the three triad legs per request → CI thresholds (e.g. groundedness ≥ 0.95) → production drift alerts.

## 7.6 Semantic caching
A semantic cache embeds the new prompt and compares meaning, not text, so "Capital of France?" and "Tell me France's capital city" hit the same entry. A hit skips the LLM: no cost, no tokens, milliseconds instead of seconds.

```
query → embed → vector search
   distance < threshold → HIT  → return cached answer
   else                 → MISS → run agent → store (embedding + answer)
distance = 1 − cosine_similarity   (≈0 identical, ≈1 unrelated)
```
**Why it matters for agents:** repeated thought/action loops (cache sub-results), high latency of multi-step runs, protection of LLM/API rate limits, and consistent behaviour across rephrasings.

**This project:** L1 `OrderedDict` LRU (100 entries, exact, <1 ms, lost on restart); L2 Redis cosine ≥ 0.85, TTL 1 h, hits promote to L1, fails open if Redis is down. Key is query-only so non-deterministic routing can't fragment it; errors are never cached; travel research is cached by `travel:origin:dest:start:end`.

| Risk | Example | Mitigation |
|---|---|---|
| Real-time data | "Server status right now?" | Tag entries; bypass cache for live-data intents |
| Staleness | Flight prices change | Short TTL |
| False positives | "Charge my card" vs "Do not charge my card" | High threshold (≥ 0.92 suggested), tighter embeddings, cheap verification |

**Trade-off to own:** 0.85 is permissive for a general MiniLM model; tune with labelled paraphrase/negation pairs rather than guessing. L2 does a linear scan; a Redis vector index (RediSearch/redisvl, HNSW) is the scalable form.

## 7.7 Model routing & cost
A cheap LLM classifies queries as simple/moderate/complex; simple and moderate go to the Flash tier, complex to Pro. The cache runs **before** the router so hits pay for no classification. `CostTracker` logs model, token estimate (chars/4), USD and cache-hit flag to SQLite. Classifier provider is togglable (Gemini default, Groq Llama 3.3).
**Current state:** both routed models are flash-lite and `ENABLE_ROUTER=False`, so routing is wired but inactive; costs are estimates; no per-agent breakdown yet.

## 7.8 Security
- **Indirect prompt injection:** scraped pages are an attack surface. 12 regex patterns redact "ignore previous instructions", role overrides, INST tags, DAN, etc. before text reaches the model or memory. A test found "Ignore all previous instructions" evaded the original regex (stacked qualifiers); fixed and covered.
- **Limits:** regex is a speed bump, not a defence (paraphrase, other languages, encoding). Layer it with least-privilege tools, output validation, allow-listed actions and human approval before side effects.
- The HITL gate is in the service layer, so the LLM can never "confirm" for the user. Tool output is length-capped. Secrets belong in a secrets manager before sharing.

## 7.9 Multi-agent, MCP & human-in-the-loop
- **Agent A (Researcher):** returns validated Pydantic `ResearchResult`; parallel flights ‖ hotels ‖ attractions with a semaphore, per-tool timeout and partial-failure degradation.
- **Agent B (Coordinator):** parses intent, checks the calendar *before* research (cheap constraint first, expensive work second), delegates, merges.
- **Agent C (Booker):** deterministic itinerary (no LLM, no hallucinated prices); pauses at `awaiting_approval`; writes the calendar event only after confirm.

```
running ─► awaiting_approval ─ confirm ─► completed (calendar event created)
                             ─ cancel  ─► cancelled
                             ─ edit …  ─► running → coordinator re-run → awaiting_approval
```
- Approval lives in `ChatService` status, not the prompt. If the calendar write fails the status stays `awaiting_approval`, so confirm is retryable.
- **MCP** is a standard protocol for exposing tools/data to agents. The calendar is called directly here, with a tool definition kept so it can move behind a real MCP server; a local `mcp/` package was avoided because it would shadow the PyPI `mcp` package.
- Calendar failure fails open with an explicit "not checked" note: availability over safety, a conscious trade-off.

## 7.10 Production hardening
| Area | Done | Next |
|---|---|---|
| Retries | tenacity on 429s | Retry only idempotent calls; circuit breaker |
| Degradation | Partial research, sequential fallback, L2 fails open | Fallback providers |
| Rate limits | `Semaphore(5)` on tools | Global LLM queue / token bucket |
| Poisoning | Sanitiser + output cap | Output schema validation, allow-lists |
| Data lifecycle | Session cleanup (SQLite + Chroma) | PII handling, retention policy |
| Health | `health.check_health()`, optional `/health` | Metrics, alerts |
| Testing | 17 offline tests, 10 live travel benchmarks | Tests for Phases 1–5; golden dataset |

## 7.11 Interview Q&A
**Q1. What is RAG and why use it instead of fine-tuning?** RAG retrieves relevant documents at query time and conditions the model on them. Use it when knowledge is large, private or changing, you need citations, and you want cheap updates (re-index, no retraining). Fine-tune to change behaviour, style or vocabulary. They combine well: fine-tune for behaviour, RAG for facts.

**Q2. What is the RAG Triad?** Three checks over query, context and answer: context relevance (retrieval), groundedness (answer supported by context), answer relevance (answer addresses the question). Low scores point to retrieval, grounding or prompt/intent respectively.

**Q3. Groundedness is 100% but users say answers are wrong. Why?** The retrieved context was wrong or off-topic and the model faithfully repeated it, so context relevance is low. Also check stale data and entity mix-ups. Fix retrieval before touching the prompt.

**Q4. How do you measure groundedness, and what is wrong with cosine similarity for it?** Decompose the answer into atomic claims and verify each against context with an NLI model or LLM judge. Cosine only measures topical closeness: a false claim reusing the context's vocabulary scores high, a valid inference scores low. `hallucination.py` uses it as a cheap first filter; claim-level verification would be the rigorous step.

**Q5. How do you evaluate retrieval?** Labelled (query → relevant chunk ids) pairs; Recall@k, precision@k, MRR, nDCG. Tune chunk size, K, embedding model, hybrid search and re-ranking against these numbers.

**Q6. Why chunk with overlap, and how were 400 words / 20% chosen?** Large chunks give blurry embeddings, tiny ones lose context; overlap keeps boundary sentences. 400/20% is a sensible default, not a tuned value. I'd sweep sizes against Recall@k.

**Q7. How do you reduce hallucination here?** Ground answers in tool results via RAG; "use only provided information" prompts; Pydantic-validated structured output; deterministic itinerary formatting; judge and grounding checks in evals; human approval before actions.

**Q8. Why check the cache before the router?** A router call is an LLM call, so a hit should cost nothing. The query-only key stops a non-deterministic classifier splitting entries. The earlier order paid for classification on every hit.

**Q9. Semantic cache risks and threshold tuning?** Stale answers, real-time queries, false positives like negations. Use TTL, intent tagging and a high threshold. Tune with labelled pairs (paraphrases must hit; negations and different entities must miss) and choose from a precision–recall curve, favouring precision because a wrong hit is worse than a miss.

**Q10. How do you stop an agent looping or burning budget?** Iteration cap, cheaper models for easy queries, caching, truncated tool output, bounded retries, cost logging; parallel tools bounded by a semaphore and timeouts.

**Q11. Why is approval a state machine, not a prompt rule?** LLMs can be talked out of instructions. A stored status routes confirm/cancel/edit before any agent runs, so side effects can't happen without an explicit user action.

**Q12. Why structured output between agents?** Free text forces re-parsing and risks silent errors. Pydantic validation fails fast, so garbage doesn't propagate. Pair with JSON mode and a retry/fallback.

**Q13. Why check the calendar before research?** Cheap constraint first, expensive work second: a conflict avoids LLM and API spend. The same applies to auth, quota and policy checks.

**Q14. How do you test non-deterministic LLM behaviour?** Deterministic unit tests with fakes for orchestration/state (17 offline tests); benchmark suites with keyword and structural checks; judge and triad scoring with CI thresholds; compare scores against a baseline to catch regressions.

**Q15. Where does this not scale?** SQLite/Chroma files → Postgres + managed vector DB; L2 linear scan → vector index; per-process L1 → shared cache; threaded blocking tools → async clients; estimated costs → provider usage metadata; `.env` → secrets manager; add authN/Z and per-user isolation.

**Q16. What would you improve first?** (1) Score all three triad legs on a golden dataset, (2) hybrid retrieval + re-ranking + similarity cut-off, (3) claim-level groundedness, (4) tune the cache threshold with labelled data, (5) enable and validate the router with real tiers, (6) real booking integration behind the approval gate.

## 7.12 Cheatsheet
- **Numbers:** 400-word chunks · 20% overlap · top-K 3 · 10-turn window · 8000-token cap · L1 100 · L2 cosine 0.85, TTL 1 h · 4 iterations · 10 benchmarks · pass ≥ 0.7.
- **Triad:** right context? answer from the context? answer to the question?
- **Cache:** embed → nearest neighbour → distance below threshold ⇒ skip the LLM.
- **Agent safety:** validate first, side effects last, human approves, service layer decides.
- **Be candid about:** router inactive, dense-only retrieval, proxy groundedness, no live end-to-end run yet, booking limited to a calendar event.
