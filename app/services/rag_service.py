"""RAG service — embed, retrieve (dense / hybrid / HyDE), rerank, spotlight, generate, validate."""

from app.config import settings
from app.models import ChatResponse
from app.security.output_validator import validate_with_retry
from app.security.spotlighting import build_spotlighted_context
from app.security.system_prompt import build_system_prompt
from app.services.embedding_service import embed_texts
from app.services.hyde import HyDERetriever
from app.services.llm_service import generate
from app.services.reranking import Reranker
from app.services.vector_store import hybrid_search, search


def run_rag(question: str, flags: dict | None = None) -> ChatResponse:
    """Run the RAG pipeline with optional HyDE, hybrid search, and reranking.

    1. Retrieve chunks (dense / hybrid / HyDE)
    2. Rerank (optional)
    3. Spotlight chunks
    4. Generate answer with LLM
    5. Validate output schema
    """
    flags = flags or {}
    top_k = flags.get("top_k", 5)
    search_mode = flags.get("search_mode", "dense")
    enable_hyde = flags.get("enable_hyde", False)
    enable_rerank = flags.get("enable_rerank", True)

    # 1. Retrieve
    if enable_hyde:
        chunks = HyDERetriever().retrieve(question, top_k=top_k)
    elif search_mode == "hybrid":
        embeddings = embed_texts([question])
        query_embedding = embeddings[0]
        chunks = hybrid_search(
            query_embedding=query_embedding,
            query_text=question,
            top_k=top_k,
            rrf_k=settings.rrf_k,
        )
    elif search_mode == "sparse":
        # Sparse-only: use hybrid_search but we'll implement a sparse-only path
        # For now, fall back to dense since sparse-only needs a different interface
        embeddings = embed_texts([question])
        query_embedding = embeddings[0]
        chunks = hybrid_search(
            query_embedding=query_embedding,
            query_text=question,
            top_k=top_k,
            rrf_k=settings.rrf_k,
        )
    else:
        # dense
        embeddings = embed_texts([question])
        query_embedding = embeddings[0]
        chunks = search(query_embedding, top_k=top_k)

    # 2. Rerank
    if enable_rerank and chunks:
        chunks = Reranker().rerank(question, chunks, top_k=top_k)

    # 3. Spotlight
    spotlighted = build_spotlighted_context(chunks)

    # 4. Generate
    system = build_system_prompt()
    user_msg = f"{spotlighted}\n\nQuestion: {question}"
    result = generate(system, user_msg)
    raw = result["text"]

    # 5. Validate
    def _retry_llm(prompt: str, error: str) -> str:
        return generate(system, prompt)["text"]

    validated = validate_with_retry(raw, llm_fn=_retry_llm)
    return validated
