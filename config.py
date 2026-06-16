import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Model config — swap here to change provider later
LLM_MODEL = "gemini-2.5-flash"
MAX_ITERATIONS = 5        # safety cap on the ReAct loop
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