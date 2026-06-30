from router.classifier import classify_complexity
from config import GEMINI_FLASH_MODEL, GEMINI_PRO_MODEL

# Routing table — change thresholds here without touching any other file
ROUTING_TABLE = {
    "simple":   GEMINI_FLASH_MODEL,
    "moderate": GEMINI_FLASH_MODEL,   # Flash handles moderate well
    "complex":  GEMINI_PRO_MODEL,
}


class ModelRouter:
    """
    Classifies incoming query and returns the appropriate model name.
    Keeps routing logic in one place — easy to extend later
    (e.g. add latency-budget routing, user-tier routing).
    """

    def route(self, query:str)-> tuple[str, str]:
        """
        Returns (model_name, complexity_label).
        Both values useful — model_name for the LLM call,
        complexity_label for logging.
        """

        complexity = classify_complexity(query)
        model = ROUTING_TABLE[complexity]
        print(f"[Router]->{model}")
        return model, complexity

