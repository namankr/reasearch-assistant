import json
import llm_counter
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception

from agent.react_agent import _client, is_rate_limit_error
from config import GEMINI_FLASH_MODEL


@retry(
    wait=wait_random_exponential(min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def _generate(prompt: str, model: str):
    llm_counter.increment()
    return _client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )


def generate_json(prompt: str, model: str = None):
    """One-shot (no tools) Gemini call that must return JSON. Raises on invalid JSON."""
    response = _generate(prompt, model or GEMINI_FLASH_MODEL)
    return json.loads(response.text)
