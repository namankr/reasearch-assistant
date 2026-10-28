import sqlite3
import json
import uuid
from datetime import datetime, timedelta, timezone
from config import DB_PATH
import tiktoken
from config import MAX_HISTORY_TURNS, MAX_CONTEXT_TOKENS



class ChatService:
    """
    Stateful, persistent chat service.
    project_id  — namespaces sessions so multiple projects share one DB
    session_id  — one conversation thread; auto-generated if not provided
    """
    def __init__(self, project_id:str, session_id:str = None):
        self.project_id = project_id
        self.session_id = session_id or str(uuid.uuid4())
        self._init_db()
    
    def _init_db(self):
        with self._conn() as conn:
             conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    project   TEXT NOT NULL,
                    session   TEXT NOT NULL,
                    role      TEXT NOT NULL,
                    content   TEXT NOT NULL,
                    ts        TEXT NOT NULL
                )
            """)
             conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session   TEXT PRIMARY KEY,
                    project   TEXT NOT NULL,
                    status    TEXT DEFAULT 'running',
                    context   TEXT DEFAULT '{}',
                    updated   TEXT
                )
            """)

    def _conn(self):
        return sqlite3.connect(DB_PATH)

    def save_message(self, role:str, content: str):
        """Persist a single message immediately."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (project, session, role, content, ts) VALUES (?,?,?,?,?)",
                (self.project_id, self.session_id, role, content,
                 datetime.utcnow().isoformat())
            )
    
    def load_history(self, last_n: int = None)-> list[dict]:
        """
        Return conversation history as a list of {role, content} dicts.
        last_n=None  → full history
        last_n=20    → sliding window of last 20 turns (used in Phase 2)
        """
        with self._conn() as conn:
            if last_n:
                rows = conn.execute("""
                    SELECT role, content FROM (
                        SELECT role, content, ts FROM messages
                        WHERE project=? AND session=?
                        ORDER BY ts DESC LIMIT ?
                    ) ORDER BY ts ASC
                """, (self.project_id, self.session_id, last_n)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT role, content FROM messages WHERE project=? AND session=? ORDER BY ts ASC",
                    (self.project_id, self.session_id)
                ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]
    
    def clear_session(self):
        """Wipe this session's history (useful for testing)."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM messages WHERE project=? AND session=?",
                (self.project_id, self.session_id)
            )
    
    def load_history_windowed(self) -> list[dict]:
        """
        Sliding window: return only the last MAX_HISTORY_TURNS messages.
        This is what gets injected into every LLM call from Phase 2 onward.
        """
        return self.load_history(last_n=MAX_HISTORY_TURNS)

    def count_tokens(self, messages: list[dict]) -> int:
        """
        Count tokens across a list of {role, content} messages.
        Uses cl100k_base tokeniser — close enough for Gemini estimation.
        """
        enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for msg in messages:
            total += len(enc.encode(msg.get("content", "")))
            total += 4  # per-message overhead
        return total
    
    def build_context(self, extra_context: str="")->list[dict]:
        """
        Build the full context to pass the LLM:
        1. Sliding window of recent histoy
        2. optionally prepend retrived memory (RAG)
        warns if approaching token limit
        """
        history = self.load_history_windowed()
        token_count = self.count_tokens(history)

        print(f"[context]{len(history)} turns, ~{token_count} tokens in window")

        if token_count > MAX_CONTEXT_TOKENS * 0.85:
            print(f"[context] ⚠️  Approaching token limit ({token_count}/{MAX_CONTEXT_TOKENS})")
        
        # prepend RAG context as a system-style message if provided
        if extra_context:
            history= [{
                "role":"user",
                "content": f"[Relevant past findings for context]\n{extra_context}"
            }] + history
        return history

# ── Helpers ────────────────────────────────────────────────────────────

    def get_session_id(self) -> str:
        return self.session_id

    # ── Phase 8: session state machine + shared agent context ───────────────

    def _ensure_session_row(self, conn):
        conn.execute(
            "INSERT OR IGNORE INTO sessions (session, project, updated) VALUES (?,?,?)",
            (self.session_id, self.project_id, datetime.now(timezone.utc).isoformat())
        )

    def get_status(self) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM sessions WHERE session=? AND project=?",
                (self.session_id, self.project_id)
            ).fetchone()
        return row[0] if row else "running"

    def set_status(self, status: str):
        with self._conn() as conn:
            self._ensure_session_row(conn)
            conn.execute(
                "UPDATE sessions SET status=?, updated=? WHERE session=? AND project=?",
                (status, datetime.now(timezone.utc).isoformat(),
                 self.session_id, self.project_id)
            )

    def _load_context(self, conn) -> dict:
        row = conn.execute(
            "SELECT context FROM sessions WHERE session=? AND project=?",
            (self.session_id, self.project_id)
        ).fetchone()
        return json.loads(row[0]) if row and row[0] else {}

    def set_context(self, key: str, value):
        """Store JSON-serialisable shared state between agents."""
        with self._conn() as conn:
            self._ensure_session_row(conn)
            ctx = self._load_context(conn)
            ctx[key] = value
            conn.execute(
                "UPDATE sessions SET context=?, updated=? WHERE session=? AND project=?",
                (json.dumps(ctx), datetime.now(timezone.utc).isoformat(),
                 self.session_id, self.project_id)
            )

    def get_context(self, key: str):
        with self._conn() as conn:
            return self._load_context(conn).get(key)

    def delete_sessions_older_than(self, days: int) -> list[str]:
        """
        Delete this project's sessions (messages + state) not touched in `days`.
        Returns the deleted session ids so callers can purge vector memory too.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            stale = [r[0] for r in conn.execute(
                """SELECT session FROM (
                       SELECT session, MAX(ts) AS last FROM (
                           SELECT session, ts FROM messages WHERE project=?
                           UNION ALL
                           SELECT session, updated AS ts FROM sessions WHERE project=?
                       ) GROUP BY session
                   ) WHERE last < ?""",
                (self.project_id, self.project_id, cutoff)
            ).fetchall()]
            for sid in stale:
                conn.execute("DELETE FROM messages WHERE project=? AND session=?",
                             (self.project_id, sid))
                conn.execute("DELETE FROM sessions WHERE project=? AND session=?",
                             (self.project_id, sid))
        return stale

    def list_sessions(self) -> list[str]:
        """List all session IDs for this project."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT session FROM messages WHERE project=? ORDER BY MIN(ts)",
                (self.project_id,)
            ).fetchall()
        return [r[0] for r in rows]