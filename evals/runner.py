import sys
import sqlite3
from datetime import datetime

from chat.service import ChatService
from agent.react_agent import run_agent
from router.model_router import ModelRouter
from evals.benchmark import BENCHMARKS
from evals.judge import judge, keyword_check
from evals.hallucination import check_hallucination
from config import DB_PATH, EVAL_PASS_THRESHOLD

# Separate project_id so evals never pollute production memory
PROJECT_ID = "research_agent_eval"


def _init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eval_results (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                run_ts              TEXT,
                benchmark_id        TEXT,
                query               TEXT,
                answer              TEXT,
                kw_passed           INTEGER,
                accuracy            REAL,
                completeness        REAL,
                hallucination_risk  REAL,
                hallucination_rate  REAL,
                judge_reason        TEXT
            )
        """)


def run_evals(verbose: bool = True):
    _init_db()
    router = ModelRouter()
    run_ts = datetime.utcnow().isoformat()
    results = []

    print(f"\n{'='*60}")
    print(f"  EVAL RUN — {run_ts}")
    print(f"{'='*60}\n")

    for bench in BENCHMARKS:
        bid   = bench["id"]
        query = bench["query"]
        print(f"[{bid}] {query}")

        # Fresh session per benchmark — no cross-contamination between tests
        chat = ChatService(project_id=PROJECT_ID)
        sid  = chat.get_session_id()

        model_name, _ = router.route(query)

        # Always bypass cache for evals — we want a live agent run
        chat.save_message("user", query)
        answer = run_agent(
            user_query=query,
            history=chat.build_context(),
            session_id=sid,
            project_id=PROJECT_ID,
            model_name=model_name
        )
        chat.save_message("assistant", answer)

        # ── Score ──────────────────────────────────────────────────────
        kw      = keyword_check(answer, bench)
        scores  = judge(query, answer)
        hall    = check_hallucination(answer, sid, PROJECT_ID)

        row = {
            "run_ts":             run_ts,
            "benchmark_id":       bid,
            "query":              query,
            "answer":             answer,
            "kw_passed":          int(kw["passed"]),
            "accuracy":           scores.get("accuracy", 0),
            "completeness":       scores.get("completeness", 0),
            "hallucination_risk": scores.get("hallucination_risk", 10),
            "hallucination_rate": hall["hallucination_rate"],
            "judge_reason":       scores.get("reason", "")
        }
        results.append(row)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO eval_results
                (run_ts, benchmark_id, query, answer, kw_passed,
                 accuracy, completeness, hallucination_risk,
                 hallucination_rate, judge_reason)
                VALUES (:run_ts, :benchmark_id, :query, :answer, :kw_passed,
                        :accuracy, :completeness, :hallucination_risk,
                        :hallucination_rate, :judge_reason)
            """, row)

        status = "✓" if kw["passed"] else "✗"
        print(f"  {status}  kw={kw['passed']} | "
              f"acc={row['accuracy']}/10 | "
              f"hall_risk={row['hallucination_risk']}/10 | "
              f"hall_rate={row['hallucination_rate']}")

        if verbose and hall["risky_claims"]:
            print(f"  ⚠  Risky claims:")
            for rc in hall["risky_claims"][:2]:
                print(f"     [{rc['score']}] {rc['claim']}")

        print()

    # ── Summary ────────────────────────────────────────────────────────
    passed    = sum(1 for r in results if r["kw_passed"])
    pass_rate = passed / len(results)
    avg_acc   = sum(r["accuracy"] for r in results) / len(results)
    avg_hall  = sum(r["hallucination_risk"] for r in results) / len(results)

    print(f"{'='*60}")
    print(f"  RESULTS : {passed}/{len(results)} passed ({pass_rate*100:.0f}%)")
    print(f"  Avg accuracy           : {avg_acc:.1f}/10")
    print(f"  Avg hallucination risk : {avg_hall:.1f}/10")
    print(f"  CI threshold           : {EVAL_PASS_THRESHOLD*100:.0f}%")

    if pass_rate >= EVAL_PASS_THRESHOLD:
        print(f"  STATUS  : ✓ PASS")
    else:
        print(f"  STATUS  : ✗ FAIL — below threshold")
        sys.exit(1)   # non-zero exit for CI pipelines

    print(f"{'='*60}\n")
    return results


if __name__ == "__main__":
    run_evals()