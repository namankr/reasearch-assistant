from collections import OrderedDict
from config import L1_MAX_SIZE

class MemoryCache:
    """
    L1 in-memory exact-match cache.
    Uses an OrderedDict so we can evict the oldest entry when full (LRU).
    Wiped on process restart — that's expected and fine.
    """

    def __init__(self):
        self._store: OrderedDict[str, str] = OrderedDict()

    def _key(self, query:str):
        # Cache is keyed on the normalized query only — independent of which
        # model answered it, so routing decisions can't fragment the cache.
        return query.strip().lower()
    
    def get(self, query: str) -> str | None:
        key = self._key(query)
        if key in self._store:
            # Move to end (most recently used)
            self._store.move_to_end(key)
            print(f"[Cache L1] Hit for: '{query[:60]}'")
            return self._store[key]
        return None

    def set(self, query: str, answer: str):
        key = self._key(query)
        self._store[key] = answer
        self._store.move_to_end(key)
        # Evict oldest if over size limit
        if len(self._store) > L1_MAX_SIZE:
            evicted = self._store.popitem(last=False)
            print(f"[Cache L1] Evicted oldest entry (size limit reached)")
        print(f"[Cache L1] Stored: '{query[:60]}'")

    def size(self) -> int:
        return len(self._store)