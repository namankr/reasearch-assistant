import sys

from agent.travel_pipeline import handle_user_message
from chat.service import ChatService
from config import EVAL_PASS_THRESHOLD
from evals.travel_benchmarks import TRAVEL_BENCHMARKS, evaluate

# Uses the real travel_agent project: the pipeline is hard-wired to it, so eval sessions
# are fresh UUIDs but share the DB. Run against a scratch DB_PATH if that matters.
PROJECT_ID = "travel_agent"


def run_travel_evals() -> list[dict]:
    results = []
    for bench in TRAVEL_BENCHMARKS:
        chat = ChatService(project_id=PROJECT_ID)
        sid = chat.get_session_id()
        response = ""
        try:
            for turn in bench["turns"]:
                response = handle_user_message(turn, sid)
        except Exception as e:
            response = f"ERROR: {e}"
        verdict = evaluate(bench, response, chat.get_status())
        results.append({"id": bench["id"], **verdict})
        print(f"[{bench['id']}] {'PASS' if verdict['passed'] else 'FAIL'} "
              f"{verdict['missing_keywords'] or ''} {verdict['failed_checks'] or ''}")

    pass_rate = sum(r["passed"] for r in results) / len(results)
    print(f"\nTravel evals: {pass_rate*100:.0f}% passed (threshold {EVAL_PASS_THRESHOLD*100:.0f}%)")
    if pass_rate < EVAL_PASS_THRESHOLD:
        sys.exit(1)
    return results


if __name__ == "__main__":
    run_travel_evals()
