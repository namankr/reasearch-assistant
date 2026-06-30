import json
import uuid
import numpy as np
import redis
from sentence_transformers import SentenceTransformer
from config import (REDIS_HOST, REDIS_PORT, REDIS_TTL_SECONDS,
                    CACHE_SIMILARITY_THRESHOLD, EMBEDDING_MODEL)

class RedisSemanticCache:
    """
    L2 semantic cache backed by Redis.
    Stores query embeddings + answers.
    On lookup, finds the most similar cached query by cosine similarity.
    Falls back gracefully if Redis is unavailable.
    """

    def __init__(self):
        self._model = SentenceTransformer(EMBEDDING_MODEL)
        self._redis = self._connect()

    def _connect(self):
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            print("[cache L2] Redis connected")
            return client
        except Exception as e:
            print(f"[Cache L2] Redis unavailable — L2 cache disabled: {e}")
            return None
    
    def _embed(self, text:str)->list[float]:
        return self._model.encode(text).tolist()
    
    def cosine(self, a:list[float], b:list[float])-> float:
        va, vb = np.array(a), np.array(b)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        return float(np.dot(va, vb)/denom) if denom else 0.0

    # ── Public interface ──────────────────────────────────────────────────

    def get(self, query:str, model:str)-> str | None:
        if not self._redis:
            return
        query_vec = self._embed(query)
        # Scan all cached entries for this model
        pattern = f"cache:{model}:*"
        best_score, best_answer = 0.0, None

        for key in self._redis.scan_iter(pattern):
            try:
                raw = self._redis.get(key)
                if not raw :
                    continue
                entry = json.loads(raw)
                score = self.cosine(query_vec, entry["embedding"])
                if score > best_score:
                    best_answer = entry["answer"]
            except Exception:
                continue
        
        if best_score >= CACHE_SIMILARITY_THRESHOLD and best_answer:
            print(f"[Cache L2] Semantic hit (score: {best_score:.3f}) "
                  f"for: '{query[:60]}'")
            return best_answer

        print(f"[Cache L2] Miss (best score: {best_score:.3f}) "
              f"for: '{query[:60]}'")
        return None
    
    def set(self, query:str, model:str, answer:str):
        if not self._redis:
            return
        
        entry = {
            "query": query,
            "embedding": self._embed(query),
            "answer": answer,
            "model":model
        }

        key = f"cache:{model}:{uuid.uuid4()}"
        self._redis.setex(key, REDIS_TTL_SECONDS, json.dumps(entry))
        print(f"[Cache L2] Stored with TTL={REDIS_TTL_SECONDS}s: "
              f"'{query[:60]}'")
    
    @property
    def available(self) -> bool:
        return self._redis is not None
    