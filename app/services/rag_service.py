"""RAG service — Lesson 5: + CRAG corrective grading + web fallback.

L4 had dense/sparse/hybrid + rerank + HyDE. L5 adds CRAG:
  1. After retrieval, an LLM grader scores the chunks' relevance.
  2. If score < threshold AND not flagged ambiguous, fall back to a
     Tavily web search and REPLACE the chunks.
  3. If ambiguous, keep the original chunks but flag low confidence.

Flag added in this lesson:
  enable_crag: bool   (default True at the service level)
"""

from __future__ import annotations

from loguru import logger

from app.config import settings
from app.models import (
    ChatResponse,
    ResponseMetadata,
    RetrievedChunk,
    RetrievedChunkPreview,
)
from app.security.spotlighting import build_spotlighted_context
from app.security.system_prompt import build_system_prompt
from app.services.crag import crag_pipeline
from app.services.embedding_service import embed_texts
from app.services.hyde import HyDERetriever
from app.services.llm_service import generate
from app.services.reranking import Reranker
from app.services.vector_store import hybrid_search, search, sparse_search


def _flag(flags: dict | None, key: str, default):
    if not isinstance(flags, dict):
        return default
    return flags.get(key, default)


def _retrieve(question: str, flags: dict | None = None) -> list[RetrievedChunk]:
    final_top_k = int(_flag(flags, "top_k", 5))
    mode = _flag(flags, "search_mode", "dense")
    rerank = bool(_flag(flags, "enable_rerank", False))
    hyde = bool(_flag(flags, "enable_hyde", False))
    crag = bool(_flag(flags, "enable_crag", settings.crag_enabled_by_default))

    retrieve_k = settings.reranker_initial_top_k if rerank else final_top_k

    if hyde:
        chunks = HyDERetriever().retrieve(question, top_k=retrieve_k)
    elif mode == "sparse":
        chunks = sparse_search(question, top_k=retrieve_k)
    elif mode == "hybrid":
        query_embedding = embed_texts([question])[0]
        chunks = hybrid_search(query_embedding, question, top_k=retrieve_k)
    else:
        query_embedding = embed_texts([question])[0]
        chunks = search(query_embedding, top_k=retrieve_k)

    if rerank and chunks:
        chunks = Reranker().rerank(question, chunks, top_k=final_top_k)
    else:
        chunks = chunks[:final_top_k]

    # CRAG: grade chunks; on low relevance, replace with Tavily web search.
    # Returns (chunks, evaluation, web_fallback_used) — we only need chunks here.
    if crag and chunks:
        chunks, _eval, _used_web = crag_pipeline(
            question=question,
            chunks=chunks,
            enable_crag=True,
        )

    return chunks


def _generate(question: str, chunks: list[RetrievedChunk]) -> ChatResponse:
    spotlighted = build_spotlighted_context(chunks)
    system = build_system_prompt()
    user_msg = f"{spotlighted}\n\nQuestion: {question}"
    raw = generate(system, user_msg)["text"]
    chunk_previews = [
        RetrievedChunkPreview(text=c.text, source=c.source, score=c.score) for c in chunks
    ]
    return ChatResponse(
        answer=raw,
        sources=list({c.source for c in chunks}),
        confidence=0.7,
        metadata=ResponseMetadata(route="rag", retrieved_chunks=chunk_previews),
    )


def run_rag(question: str, flags: dict | int | None = None) -> ChatResponse:
    logger.info(
        "L5 RAG | mode={} rerank={} hyde={} crag={} top_k={}",
        _flag(flags, "search_mode", "dense"),
        _flag(flags, "enable_rerank", False),
        _flag(flags, "enable_hyde", False),
        _flag(flags, "enable_crag", settings.crag_enabled_by_default),
        int(_flag(flags, "top_k", 5)),
    )
    chunks = _retrieve(question, flags=flags if isinstance(flags, dict) else None)
    return _generate(question, chunks)


def run_rag_with_trace(
    question: str, flags: dict | int | None = None
) -> tuple[ChatResponse, list[RetrievedChunk]]:
    chunks = _retrieve(question, flags=flags if isinstance(flags, dict) else None)
    response = _generate(question, chunks)
    return response, chunks


run_rag_with_trace_no_cache = run_rag_with_trace
