from google import genai
from config import GEMINI_API_KEY, GEMINI_FLASH_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY)

_CLASSIFIER_PROMPT = """You are a query complexity classifier.
Classify the user query into exactly one of: simple / moderate / complex

Rules:
- simple   : factual lookup, definition, quick fact. No multi-step reasoning needed.
             Examples: "what is RAG?", "define embeddings", "who invented Python"
- moderate : requires explanation, comparison, or a few reasoning steps.
             Examples: "how does RAG compare to fine-tuning?", "explain transformer attention"
- complex  : requires deep research, multi-step analysis, synthesis across many sources.
             Examples: "build a research plan for agentic AI", "analyze pros and cons of 5 vector DBs"

Reply with ONLY one word: simple, moderate, or complex. Nothing else."""


def classify_complexity(query: str) -> str:
    """
    Use a cheap Flash call to score query complexity.
    Returns 'simple', 'moderate', or 'complex'.
    Falls back to 'moderate' on any error.
    """
    try:
        response = _client.models.generate_content(
            model=GEMINI_FLASH_MODEL,
            contents=f"{_CLASSIFIER_PROMPT}\n\nQuery: {query}"
        )
        result = response.text.strip().lower()
        if result not in ("simple", "moderate", "complex"):
            return "moderate"
        print(f"[Router] Complexity: {result} for: '{query[:60]}'")
        return result
    except Exception as e:
        print(f"[Router] Classifier error, defaulting to moderate: {e}")
        return "moderate"