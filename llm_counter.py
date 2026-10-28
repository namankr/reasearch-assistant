import threading

_lock = threading.Lock()
_count = 0


def increment() -> None:
    global _count
    with _lock:
        _count += 1


def get() -> int:
    return _count
