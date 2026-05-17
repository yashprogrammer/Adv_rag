"""RAG service with Phase 2+3 retrieval and quality controls."""

from app.config import settings
from app.models import ChatResponse, RetrievedChunk
from app.security.output_validator import validate_with_retry
from app.security.spotlighting import build_spotlighted_context
from app.security.system_prompt import build_system_prompt
from app.services.crag import crag_pipeline
from app.services.embedding_service import embed_texts
from app.services.hyde import HyDERetriever
from app.services.llm_service import generate
from app.services.query_cache_service import query_cache
from app.services.reranking import Reranker
from app.services.self_reflective import reflect_on_answer, should_regenerate
from app.services.vector_store import hybrid_search, search, sparse_search


def _retrieve(question: str, flags: dict) -> list[RetrievedChunk]:
    """Retrieve chunks for a question according to flags.

    Steps: retrieve → rerank → CRAG.
    """
    top_k = flags.get("top_k", 5)
    search_mode = flags.get("search_mode", "dense")
    enable_hyde = flags.get("enable_hyde", False)
    enable_rerank = flags.get("enable_rerank", True)
    enable_crag = flags.get("enable_crag", settings.crag_enabled_by_default)

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
        # Pure TF-IDF sparse search (no dense embeddings, no RRF fusion)
        chunks = sparse_search(query_text=question, top_k=top_k)
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

    return chunks


def _generate(
    question: str,
    chunks: list[RetrievedChunk],
    flags: dict,
) -> ChatResponse:
    """Generate a validated ChatResponse from retrieved chunks.

    Steps: spotlight → generate → reflect → validate.
    """
    enable_self_reflective = flags.get(
        "enable_self_reflective",
        settings.self_reflective_enabled_by_default,
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
    reflection_iterations = 0
    last_reflection_score: float | None = None
    final_refined_question: str | None = None
    if enable_self_reflective:
        while True:
            reflection = reflect_on_answer(
                question=working_question,
                answer=raw,
                context=spotlighted,
            )
            last_reflection_score = float(reflection.reflection_score)
            if not should_regenerate(reflection, reflection_iterations):
                break
            # Capture the refined question that drove this regeneration
            final_refined_question = reflection.refined_question or working_question
            working_question = final_refined_question
            raw = _generate_raw_answer(working_question)
            reflection_iterations += 1

    # 7. Validate
    def _retry_llm(prompt: str, error: str) -> str:
        return generate(system, prompt)["text"]

    response = validate_with_retry(raw, llm_fn=_retry_llm)

    # 8. Surface self-RAG telemetry in the response metadata so callers
    #    (UI, eval harness, demo script) can prove the loop actually ran.
    if enable_self_reflective:
        response.metadata.reflection_iterations = reflection_iterations
        response.metadata.reflection_score = last_reflection_score
        response.metadata.refined_question = final_refined_question
    return response


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
    cache_context = {
        "search_mode": flags.get("search_mode", "dense"),
        "enable_hyde": bool(flags.get("enable_hyde", False)),
        "enable_rerank": bool(flags.get("enable_rerank", True)),
        "enable_crag": bool(flags.get("enable_crag", settings.crag_enabled_by_default)),
        "enable_self_reflective": bool(
            flags.get("enable_self_reflective", settings.self_reflective_enabled_by_default)
        ),
        "top_k": int(flags.get("top_k", 5)),
    }
    cached = query_cache.get_rag_answer(question, cache_context)
    if cached is not None:
        response = ChatResponse(**cached)
        response.cache_hit = True
        return response

    chunks = _retrieve(question, flags)
    validated = _generate(question, chunks, flags)
    query_cache.set_rag_answer(question, validated.model_dump(), cache_context)
    return validated


def run_rag_with_trace(
    question: str,
    flags: dict | None = None,
) -> tuple[ChatResponse, list[RetrievedChunk]]:
    """Production-grade RAG that also returns the chunks used for tracing.

    Mirrors run_rag's caching behavior (5-tier query cache) so that the API
    path through the LangGraph benefits from cache hits.  On a cache hit,
    the returned chunks list is empty (the answer is what's cached, not
    the upstream retrieval) — callers must handle this gracefully.

    Steps:
        1. Compute cache key from (question, flags subset)
        2. Cache lookup → on hit, set response.cache_hit=True and return
        3. On miss: retrieve → rerank → CRAG → generate → cache → return
    """
    flags = flags or {}
    cache_context = {
        "search_mode": flags.get("search_mode", "dense"),
        "enable_hyde": bool(flags.get("enable_hyde", False)),
        "enable_rerank": bool(flags.get("enable_rerank", True)),
        "enable_crag": bool(flags.get("enable_crag", settings.crag_enabled_by_default)),
        "enable_self_reflective": bool(
            flags.get("enable_self_reflective", settings.self_reflective_enabled_by_default)
        ),
        "top_k": int(flags.get("top_k", 5)),
    }
    cached = query_cache.get_rag_answer(question, cache_context)
    if cached is not None:
        response = ChatResponse(**cached)
        response.cache_hit = True
        # No chunks available on cache hit — the cached payload is the answer
        # itself, not the upstream retrieval state.  Callers that need the
        # retrieved chunks should bypass cache via run_rag_with_trace_no_cache().
        return response, []

    chunks = _retrieve(question, flags)
    validated = _generate(question, chunks, flags)
    query_cache.set_rag_answer(question, validated.model_dump(), cache_context)
    return validated, chunks


def run_rag_with_trace_no_cache(
    question: str,
    flags: dict | None = None,
) -> tuple[ChatResponse, list[RetrievedChunk]]:
    """Eval-only variant that bypasses the cache.  Use for offline eval and
    diagnostic tooling where you need a guaranteed fresh retrieve+generate.
    """
    flags = flags or {}
    chunks = _retrieve(question, flags)
    validated = _generate(question, chunks, flags)
    return validated, chunks
