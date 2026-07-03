from google import genai
from config import (GEMINI_API_KEY, GEMINI_FLASH_MODEL,
                   GROQ_MODEL, CLASSIFIER_PROVIDER)
from llm.groq_client import groq_generate

_client = genai.Client(api_key=GEMINI_API_KEY)

# Active classifier backend — starts from config, can be flipped at runtime.
_active_provider = CLASSIFIER_PROVIDER

VALID_PROVIDERS = ("gemini", "groq")


def set_classifier_provider(provider: str) -> str:
    """
    Toggle the classifier LLM backend at runtime.
    provider — "gemini" or "groq". Returns the newly active provider.
    """
    global _active_provider
    provider = provider.strip().lower()
    if provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Choose from {VALID_PROVIDERS}.")
    _active_provider = provider
    print(f"[Router] Classifier provider set to: {_active_provider}")
    return _active_provider


def get_classifier_provider() -> str:
    """Return the currently active classifier provider."""
    return _active_provider


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


def _classify_gemini(query: str) -> str:
    response = _client.models.generate_content(
        model=GEMINI_FLASH_MODEL,
        contents=f"{_CLASSIFIER_PROMPT}\n\nQuery: {query}"
    )
    return response.text.strip().lower()


def _classify_groq(query: str) -> str:
    result = groq_generate(
        prompt=f"Query: {query}",
        system=_CLASSIFIER_PROMPT,
        model=GROQ_MODEL,
    )
    return result.strip().lower()


def classify_complexity(query: str) -> str:
    """
    Score query complexity using the active LLM backend (gemini or groq).
    Returns 'simple', 'moderate', or 'complex'.
    Falls back to 'moderate' on any error.
    """
    try:
        if _active_provider == "groq":
            result = _classify_groq(query)
        else:
            result = _classify_gemini(query)

        if result not in ("simple", "moderate", "complex"):
            return "moderate"
        print(f"[Router] Complexity: {result} "
              f"({_active_provider}) for: '{query[:60]}'")
        return result
    except Exception as e:
        print(f"[Router] Classifier error, defaulting to moderate: {e}")
        return "moderate"