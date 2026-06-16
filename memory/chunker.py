from config import CHUNK_SIZE

def chunk_text(text:str, source:str, session_id:str) -> list[dict]:
    """
    Split text into overlapping chunks with metadata.
    Returns list of {text, metadata} ready for ChromaDB.
    """
    chunks = []
    words = text.split()
    step = int(CHUNK_SIZE * 0.8)        # 20% overlap between chunks

    for i in range(0, len(words), step):
        chunk = " ".join(words[i: i + CHUNK_SIZE])
        if len(chunk.strip()) < 50:   # skip tiny trailing chunks
            continue
        chunks.append({
            "text": chunk,
            "metadata": {
                "source": source,
                "session_id": session_id,
                "chunk_index": len(chunks)
            }
        })
    return chunks