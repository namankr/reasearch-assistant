import re
import numpy as np
from sentence_transformers import SentenceTransformer
from memory.vector_store import VectorMemory
from config import EMBEDDING_MODEL, HALLUCINATION_THRESHOLD

_model = SentenceTransformer(EMBEDDING_MODEL)


def _cosine(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def extract_claims(answer: str) -> list[str]:
    """Split answer into individual sentences for per-claim checking."""
    sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
    return [s.strip() for s in sentences if len(s) > 30]


def check_hallucination(answer: str,
                        session_id: str,
                        project_id: str) -> dict:
    """
    For each sentence in the answer, check if it's grounded in
    the agent's retrieved source chunks stored in ChromaDB.

    A sentence with no similar chunk = hallucination flag.
    Returns: {flagged, risky_claims, grounded_claims, hallucination_rate}
    """
    memory = VectorMemory(project_id)
    claims = extract_claims(answer)
    risky, grounded = [], []

    for claim in claims:
        results = memory._collection.query(
            query_texts=[claim],
            n_results=1,
            where={"session_id": session_id}
        )
        docs = results.get("documents", [[]])[0]

        if not docs:
            # No memory at all for this session — can't ground the claim
            risky.append({
                "claim": claim[:120],
                "score": 0.0,
                "source": "no memory"
            })
            continue

        claim_vec  = _model.encode(claim).tolist()
        source_vec = _model.encode(docs[0]).tolist()
        score      = _cosine(claim_vec, source_vec)

        if score < HALLUCINATION_THRESHOLD:
            risky.append({
                "claim":  claim[:120],
                "score":  round(score, 3),
                "source": docs[0][:80]
            })
        else:
            grounded.append({
                "claim": claim[:120],
                "score": round(score, 3)
            })

    total = max(len(claims), 1)
    return {
        "flagged":            len(risky) > 0,
        "risky_claims":       risky,
        "grounded_claims":    grounded,
        "hallucination_rate": round(len(risky) / total, 2)
    }