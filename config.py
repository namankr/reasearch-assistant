import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Model config
LLM_MODEL          = "gemini-2.5-flash-lite"
MAX_ITERATIONS = 4
DB_PATH        = "agent_memory.db"

# Search provider: "ddgs" (default, no key needed) or "tavily" (requires TAVILY_API_KEY)
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "ddgs")

# Phase 2 additions
CHROMA_DB_PATH    = "./chroma_db"
EMBEDDING_MODEL   = "all-MiniLM-L6-v2"
MAX_HISTORY_TURNS = 10                 # sliding window size — single definition
MAX_CONTEXT_TOKENS = 8000
MEMORY_TOP_K      = 3
CHUNK_SIZE        = 400

# Phase 3 — Cache settings
REDIS_HOST               = "localhost"
REDIS_PORT               = 6379
REDIS_TTL_SECONDS        = 3600
CACHE_SIMILARITY_THRESHOLD = 0.85
L1_MAX_SIZE              = 100

# Phase 4 — Router settings
GEMINI_FLASH_MODEL = "gemini-2.5-flash-lite"
GEMINI_PRO_MODEL   = "gemini-2.5-flash-lite"


# Groq settings
GROQ_MODEL = "llama-3.3-70b-versatile"

# Classifier provider toggle: "gemini" or "groq"
CLASSIFIER_PROVIDER = os.getenv("CLASSIFIER_PROVIDER", "gemini").lower()

# Approximate cost per 1M tokens (USD)
FLASH_COST_PER_1M = 0.075
PRO_COST_PER_1M   = 3.50

RETRY_MAX_ATTEMPTS = 4
RETRY_BASE_DELAY   = 10

ENABLE_ROUTER = False

# Langfuse config
LANGFUSE_PUBLIC_KEY     = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY     = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST           = os.getenv("LANGFUSE_HOST")
EVAL_PASS_THRESHOLD     = 0.7
HALLUCINATION_THRESHOLD = 0.4

# SerpAPI — both names resolve to the same env var
SERPAPI_KEY     = os.getenv("SERPAPI_KEY")
SERPAPI_API_KEY = SERPAPI_KEY              # alias used by flight_search / hotel_search

# Travel tool settings
TRAVEL_RESULTS_LIMIT     = int(os.getenv("TRAVEL_RESULTS_LIMIT", "5"))
DEFAULT_TRAVEL_CURRENCY  = os.getenv("DEFAULT_TRAVEL_CURRENCY", "USD")
DEFAULT_TRAVEL_LANGUAGE  = os.getenv("DEFAULT_TRAVEL_LANGUAGE", "en")
DEFAULT_TRAVEL_COUNTRY   = os.getenv("DEFAULT_TRAVEL_COUNTRY", "us")

# Phase 9 - hardening
MAX_TOOL_OUTPUT_CHARS    = 8000
SESSION_RETENTION_DAYS   = 7
TRAVEL_CONCURRENCY       = 5      # max simultaneous outbound tool calls
TRAVEL_TOOL_TIMEOUT_S    = 30
ENABLE_PARALLEL_RESEARCH = True
