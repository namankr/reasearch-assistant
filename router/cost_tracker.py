import sqlite3
from datetime import datetime
from config import DB_PATH, FLASH_COST_PER_1M, PRO_COST_PER_1M

class CostTracker:
    """
    Logs every LLM call: model used, estimated tokens, estimated cost.
    Writes to SQLite so costs persist across sessions.
    """

    MODEL_COSTS ={
        "gemini-3.1-flash-lite":FLASH_COST_PER_1M,
        "gemini-3.1-pro":PRO_COST_PER_1M
    }

    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         TEXT,
                    model      TEXT,
                    query      TEXT,
                    tokens_est INTEGER,
                    cost_usd   REAL,
                    cache_hit  INTEGER DEFAULT 0
                )
            """)
    
    def log(self, query: str, model: str,
            tokens_est: int, cache_hit: bool = False):
        cost = (tokens_est / 1_000_000) * self.MODEL_COSTS.get(model, 0)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO cost_log (ts,model,query,tokens_est,cost_usd,cache_hit)"
                " VALUES (?,?,?,?,?,?)",
                (datetime.utcnow().isoformat(), model,
                 query[:200], tokens_est, cost, int(cache_hit))
            )

    def print_summary(self):
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute("""
                    SELECT model,
                        COUNT(*) as calls,
                        SUM(tokens_est) as tokens,
                        SUM(cost_usd) as cost,
                        SUM(cache_hit) as hits
                    FROM cost_log GROUP BY model
                """).fetchall()

            if not rows:
                return
            print("\n── Cost summary ─────────────────────────────────")
            for model, calls, tokens, cost, hits in rows:
                print(f"  {model:<28} calls={calls:>4}  "
                    f"tokens={tokens:>8,}  "
                    f"cost=${cost:.4f}  "
                    f"cache_hits={hits}")
            print("─────────────────────────────────────────────────\n")
        
    
    