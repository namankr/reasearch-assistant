def _check(fn) -> dict:
    try:
        fn()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _redis():
    import redis
    from config import REDIS_HOST, REDIS_PORT
    redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=2).ping()


def _chroma():
    import chromadb
    from config import CHROMA_DB_PATH
    chromadb.PersistentClient(path=CHROMA_DB_PATH).heartbeat()


def _sqlite():
    import sqlite3
    from config import DB_PATH
    sqlite3.connect(DB_PATH).execute("SELECT 1").fetchone()


def _gemini():
    from config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    from agent.react_agent import _client
    next(iter(_client.models.list()))


def check_health() -> dict:
    """Pings every dependency. Redis is optional (L2 cache fails open)."""
    checks = {"sqlite": _check(_sqlite), "chromadb": _check(_chroma),
              "gemini": _check(_gemini), "redis": _check(_redis)}
    required_ok = all(checks[k]["ok"] for k in ("sqlite", "chromadb", "gemini"))
    return {"status": "ok" if required_ok else "degraded", "checks": checks}


try:
    from fastapi import FastAPI
    app = FastAPI(title="Travel Agent health")

    @app.get("/health")
    def health():
        return check_health()
except ImportError:
    app = None  # pip install fastapi uvicorn to expose GET /health
