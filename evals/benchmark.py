# 10 benchmarks — expected_keywords must ALL appear in answer for a pass
# should_not_contain catches refusals and hallucinated disclaimers

BENCHMARKS = [
    {
        "id": "b01",
        "query": "What is RAG in AI?",
        "expected_keywords": ["retrieval", "augmented", "generation", "vector"],
        "should_not_contain": ["I don't know", "I cannot"],
        "category": "factual"
    },
    {
        "id": "b02",
        "query": "What is the difference between RAG and fine-tuning?",
        "expected_keywords": ["fine-tuning", "retrieval", "training", "cost"],
        "should_not_contain": [],
        "category": "comparison"
    },
    {
        "id": "b03",
        "query": "What is a vector database?",
        "expected_keywords": ["embedding", "similarity", "search"],
        "should_not_contain": [],
        "category": "factual"
    },
    {
        "id": "b04",
        "query": "How does cosine similarity work?",
        "expected_keywords": ["vector", "angle", "dot product"],
        "should_not_contain": [],
        "category": "factual"
    },
    {
        "id": "b05",
        "query": "What is the ReAct pattern in AI agents?",
        "expected_keywords": ["reasoning", "acting", "tool", "observation"],
        "should_not_contain": [],
        "category": "factual"
    },
    {
        "id": "b06",
        "query": "What is prompt injection in AI systems?",
        "expected_keywords": ["injection", "malicious", "instructions", "attack"],
        "should_not_contain": [],
        "category": "security"
    },
    {
        "id": "b07",
        "query": "What is LangGraph used for?",
        "expected_keywords": ["graph", "agent", "state"],
        "should_not_contain": [],
        "category": "factual"
    },
    {
        "id": "b08",
        "query": "What is the difference between ChromaDB and Pinecone?",
        "expected_keywords": ["chroma", "pinecone", "local", "cloud"],
        "should_not_contain": [],
        "category": "comparison"
    },
    {
        "id": "b09",
        "query": "What is token budgeting in LLMs?",
        "expected_keywords": ["token", "context", "limit", "cost"],
        "should_not_contain": [],
        "category": "factual"
    },
    {
        "id": "b10",
        "query": "What is human-in-the-loop in agentic AI?",
        "expected_keywords": ["human", "approval", "review", "oversight"],
        "should_not_contain": [],
        "category": "factual"
    },
]