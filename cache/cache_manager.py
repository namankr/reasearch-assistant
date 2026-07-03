from cache.memory_cache import MemoryCache
from cache.redis_cache import RedisSemanticCache

class CacheManager:
    """
    Two-layer cache orchestrator.
    Check L1 (fast, exact) → check L2 (slower, semantic) → miss.
    On miss: caller runs agent, then calls store() to populate both layers.
    """

    def __init__(self):
        self.l1 = MemoryCache()
        self.l2 = RedisSemanticCache()
        self.stats = {"l1_hits":0,"l2_hits":0, "misses":0}

    def get(self, query:str)-> str | None:
        # L1 first
        answer = self.l1.get(query)
        if answer:
            self.stats["l1_hits"] +=1;
            return answer
        # L2 next
        answer = self.l2.get(query)
        if answer:
            # Promote to L1 so next identical hit is instant
            self.l1.set(query, answer)
            self.stats["l2_hits"] +=1;
            return answer
        
        self.stats["misses"] += 1;
        return None

    def store(self, query: str, answer: str):
        """Store a fresh agent answer in both cache layers."""
        self.l1.set(query, answer)
        self.l2.set(query, answer)

    def print_stats(self):
        total = sum(self.stats.values())
        if total == 0:
            return
        hit_rate = (self.stats["l1_hits"] + self.stats["l2_hits"]) / total * 100
        print(f"\n[Cache Stats] "
              f"L1 hits: {self.stats['l1_hits']} | "
              f"L2 hits: {self.stats['l2_hits']} | "
              f"Misses: {self.stats['misses']} | "
              f"Hit rate: {hit_rate:.0f}%")