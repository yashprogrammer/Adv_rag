"""RAG service with Phase 2+3 retrieval and quality controls."""

from app.config import settings
from app.models import ChatResponse
from app.security.output_validator import validate_with_retry
from app.security.spotlighting import build_spotlighted_context
from app.security.system_prompt import build_system_prompt
from app.services.crag import crag_pipeline
from app.services.embedding_service import embed_texts
from app.services.hyde import HyDERetriever
from app.services.llm_service import generate
from app.services.reranking import Reranker
from app.services.self_reflective import reflect_on_answer, should_regenerate
from app.services.vector_store import hybrid_search, search


def run_rag(question: str, flags: dict | None = None) -> ChatResponse:
    """Run the RAG pipeline with optional HyDE, hybrid search, CRAG, and reflection.

    1. Retrieve chunks (dense / hybrid / HyDE)
    2. Rerank (optional)
    3. CRAG evaluation + optional web fallback
    4. Spotlight chunks
    5. Generate answer with LLM
    6. Optional self-reflection and regeneration
    7. Validate output schema
    """
    flags = flags or {}
    top_k = flags.get("top_k", 5)
    search_mode = flags.get("search_mode", "dense")
    enable_hyde = flags.get("enable_hyde", False)
    enable_rerank = flags.get("enable_rerank", True)
    enable_crag = flags.get("enable_crag", settings.crag_enabled_by_default)
    enable_self_reflective = flags.get(
        "enable_self_reflective",
        settings.self_reflective_enabled_by_default,
    )

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

    # 3. CRAG (grade relevance + optional web fallback)
    chunks, _evaluation, _used_web = crag_pipeline(
        question=question,
        chunks=chunks,
        enable_crag=enable_crag,
    )

    # 4. Spotlight
    spotlighted = build_spotlighted_context(chunks)

    # 5. Generate
    system = build_system_prompt()
    working_question = question

    def _generate_raw_answer(current_question: str) -> str:
        user_msg = f"{spotlighted}\n\nQuestion: {current_question}"
        result = generate(system, user_msg)
        return result["text"]

    raw = _generate_raw_answer(working_question)

    # 6. Self-reflective regeneration loop
    if enable_self_reflective:
        iteration = 0
        while True:
            reflection = reflect_on_answer(
                question=working_question,
                answer=raw,
                context=spotlighted,
            )
            if not should_regenerate(reflection, iteration):
                break
            working_question = reflection.refined_question or working_question
            raw = _generate_raw_answer(working_question)
            iteration += 1

    # 7. Validate
    def _retry_llm(prompt: str, error: str) -> str:
        return generate(system, prompt)["text"]

    validated = validate_with_retry(raw, llm_fn=_retry_llm)
    return validated
