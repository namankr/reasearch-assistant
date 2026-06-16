import uuid
import chromadb
from chromadb.utils import embedding_functions
from config import CHROMA_DB_PATH, EMBEDDING_MODEL, MEMORY_TOP_K
from memory.chunker import chunk_text

class VectorMemory:
    """
    Long-term memory for thr agent. Stores tool results as embeddings, retrives relevant ones
    per query.
    One collection per project - sessions are filtered by metadata.
    """

    def __init__(self, project_id:str):
        self.project_id = project_id
        self._client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        self._collection = self._client.get_or_create_collection(name=f"memory_{project_id}", embedding_function= self._ef)
    
    def store(self, text:str, source:str, session_id:str):
        """ chunk and store a tool result in vector memory"""
        chunks = chunk_text(text, source, session_id)
        if not chunks:
            return

        self._collection.add(
            documents = [c["text"] for c in chunks],
            metadatas = [c["metadata"] for c in chunks],
            ids = [str(uuid.uuid4()) for _ in chunks]
        )
        print(f"[Memory] Stored {len(chunks)} chunk(s) from:{source}")

    def retrieve(self, query:str, session_id:str, top_k:int = MEMORY_TOP_K) ->str:
        """
        Retrieve the most relevant past findings for a query. Filters to current session so projects don't bleed into 
        each other
        """
        results = self._collection.query(query_texts= [query], n_results=top_k, where={"session_id": session_id})
        docs = results.get("documents", [[]])[0]
        
        if not docs:
            return""
        
        formatted = "\n\n---\n".join(
            f"[Past finding {i+1}]: {doc}" for i, doc in enumerate(docs)
        )

        print(f"[Memory] Retrieved {len(docs)} relevant chunk(s)")
        return formatted
    
    def clear_session(self, session_id:str):
        """Remove all memory for a specific session"""
        self._collection.delete(where={"session_id": session_id})