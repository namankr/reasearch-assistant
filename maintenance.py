from chat.service import ChatService
from config import SESSION_RETENTION_DAYS


def cleanup_old_sessions(project_id: str = "travel_agent",
                         days: int = SESSION_RETENTION_DAYS) -> int:
    """Delete stale sessions from SQLite and their embeddings from ChromaDB."""
    stale = ChatService(project_id=project_id).delete_sessions_older_than(days)
    if stale:
        from agent.react_agent import get_memory
        memory = get_memory(project_id)
        for sid in stale:
            memory.clear_session(sid)
    print(f"[Maintenance] Removed {len(stale)} session(s) older than {days} day(s)")
    return len(stale)


if __name__ == "__main__":
    cleanup_old_sessions()
