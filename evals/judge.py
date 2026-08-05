import json
import re
from google import genai
from config import GEMINI_API_KEY, GEMINI_FLASH_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY)

_JUDGE_PROMPT = """You are an impartial eval judge for an AI research agent.

Given a question and the agent's answer, score it on three axes:
1. accuracy          (0-10): Is the answer factually correct?
2. completeness      (0-10): Does it cover the key aspects?
3. hallucination_risk (0-10): 10 = definitely hallucinated, 0 = well grounded

Reply in valid JSON ONLY — no markdown, no preamble:
{"accuracy": N, "completeness": N, "hallucination_risk": N, "reason": "one sentence"}"""


def judge(question: str, answer: str) -> dict:
    """Score a single agent answer. Returns score dict."""
    prompt = f"Question: {question}\n\nAgent answer:\n{answer}"
    try:
        resp = _client.models.generate_content(
            model=GEMINI_FLASH_MODEL,
            contents=f"{_JUDGE_PROMPT}\n\n{prompt}"
        )
        text = re.sub(r'```json|```', '', resp.text).strip()
        return json.loads(text)
    except Exception as e:
        return {
            "accuracy": 0, "completeness": 0,
            "hallucination_risk": 10, "reason": str(e)
        }


def keyword_check(answer: str, benchmark: dict) -> dict:
    """
    Fast deterministic check — no LLM needed.
    Returns {passed, missing_keywords, forbidden_found}
    """
    answer_lower = answer.lower()
    missing   = [kw for kw in benchmark["expected_keywords"]
                 if kw.lower() not in answer_lower]
    forbidden = [kw for kw in benchmark.get("should_not_contain", [])
                 if kw.lower() in answer_lower]
    return {
        "passed": not missing and not forbidden,
        "missing_keywords": missing,
        "forbidden_found": forbidden
    }