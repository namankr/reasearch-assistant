import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")
# Model config — swap here to change provider later
LLM_MODEL = "gemini-2.5-flash"
MAX_ITERATIONS = 4        # safety cap on the ReAct loop
MAX_HISTORY_TURNS = 10     # sliding window (used from Phase 2 onward)
DB_PATH = "agent_memory.db"

# Search provider: "ddgs" (default, no key needed) or "tavily" (requires TAVILY_API_KEY)
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "ddgs")

# Phase 2 additions
CHROMA_DB_PATH = "./chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # free, runs locally, fast
MAX_HISTORY_TURNS = 10                  # sliding window size
MAX_CONTEXT_TOKENS = 8000              # leave headroom below Gemini's limit
MEMORY_TOP_K = 3                        # how many chunks to retrieve from vector DB
CHUNK_SIZE = 400                        # chars per memory chunk


# Phase 3 — Cache settings
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_TTL_SECONDS = 3600          # 1 hour — tweak per query type later
CACHE_SIMILARITY_THRESHOLD = 0.85 # cosine score above this = cache hit
L1_MAX_SIZE = 100                  # max entries in in-memory dict

# Phase 4 — Router settings
GEMINI_FLASH_MODEL = "gemini-3.1-flash-lite"
GEMINI_PRO_MODEL   = "gemini-3.1-pro"

# Groq settings
GROQ_MODEL = "llama-3.3-70b-versatile"

# Classifier provider toggle: "gemini" or "groq"
# Override via CLASSIFIER_PROVIDER in .env, or flip at runtime with
# router.classifier.set_classifier_provider().
CLASSIFIER_PROVIDER = os.getenv("CLASSIFIER_PROVIDER", "gemini").lower() # groq for groq
# Approximate cost per 1M tokens (USD) — update if Gemini pricing changes
FLASH_COST_PER_1M  = 0.075
PRO_COST_PER_1M    = 3.50


RETRY_MAX_ATTEMPTS = 4
RETRY_BASE_DELAY   = 10   # seconds — Gemini free tier needs longer waits

ENABLE_ROUTER = True