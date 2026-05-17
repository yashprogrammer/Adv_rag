"""Query endpoint backed by LangGraph orchestration."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command

from app.config import settings
from app.core.graph import graph
from app.middleware.auth import User, get_current_user
from app.middleware.rate_limiter import is_allowed_user
from app.models import (
    ChatResponse,
    PendingSQLBlock,
    QueryRequest,
    ResponseMetadata,
    RetrievedChunkPreview,
)
from app.security.content_moderation import moderate_and_redact
from app.security.input_guard import check_input_safe
from app.security.input_restructuring import count_tokens, restructure_input
from app.security.output_validator import validate_with_retry
from app.security.token_budget import check_budget, consume_budget
from app.services.llm_service import generate

router = APIRouter(tags=["query"])


def _estimate_tokens(question: str) -> int:
    """Estimate total tokens for budget check."""
    return count_tokens(question) + settings.reserved_output_tokens


@router.post("/query")
async def query(req: QueryRequest, user: User = Depends(get_current_user)) -> ChatResponse:
    # L4b: Rate limit
    allowed, _, _ = is_allowed_user(
        user.username,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # L6: Token budget check
    estimated_tokens = _estimate_tokens(req.question)
    ok, remaining = check_budget(user.username, estimated_tokens)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"You have {remaining} tokens remaining today; this request estimated to use {estimated_tokens}.",
        )

    # L5: Input restructuring
    restructured, method_label = restructure_input(req.question)

    # L2: llm-guard scan
    guard_allowed, guard_reason = check_input_safe(restructured)
    if not guard_allowed:
        raise HTTPException(status_code=400, detail=f"injection_blocked: {guard_reason}")

    # L7a: Input moderation
    mod_allowed, moderated_text, mod_reason = moderate_and_redact(restructured)
    if not mod_allowed:
        raise HTTPException(status_code=400, detail=f"content_blocked: {mod_reason}")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(
        {
            "question": moderated_text,
            "user_id": user.username,
            "flags": req.model_dump(),
            "retrieved_chunks": [],
            "sources": [],
            "cache_hits": {},
            "cost_saved_usd": 0.0,
        },
        config=config,
    )

    # L7b: Output moderation + PII redact
    raw_answer = result.get("final_answer", "")
    out_allowed, redacted_answer, out_reason = moderate_and_redact(raw_answer)
    if not out_allowed:
        raise HTTPException(status_code=500, detail=f"output_blocked: {out_reason}")

    # L9: Output schema validate
    system_prompt = "Return a JSON object with answer, sources, and confidence fields."

    def _retry_llm(prompt: str, error: str) -> str:
        return generate(system_prompt, prompt)["text"]

    try:
        validated = validate_with_retry(redacted_answer, llm_fn=_retry_llm)
        final_answer = validated.answer
        final_confidence = validated.confidence
    except Exception:
        final_answer = redacted_answer
        final_confidence = result.get("confidence", 0.0)
    # Sources are the actual retrieved-chunk filenames from the graph state,
    # not whatever the validator-retry LLM fabricated. Trusting the LLM here
    # produces hallucinated source names like "Company Return Policy Document".
    final_sources = result.get("sources", [])

    # L6c: Token budget consume
    consume_budget(user.username, estimated_tokens)

    # Check if graph paused at SQL approval
    if "__interrupt__" in result:
        interrupt_data = result["__interrupt__"][0].value
        return ChatResponse(
            answer="",
            sources=[],
            confidence=0.0,
            pending_sql=PendingSQLBlock(
                sql=interrupt_data.get("sql", ""),
                query_id=thread_id,
                explanation=interrupt_data.get("explanation", ""),
            ),
            cache_hit=False,
            cost_saved="$0.00",
            metadata=ResponseMetadata(route="sql", restructure_method=method_label),
        )

    chunk_previews = [
        RetrievedChunkPreview(**c) for c in result.get("chunk_previews", []) or []
    ]
    return ChatResponse(
        answer=final_answer,
        sources=final_sources,
        confidence=final_confidence,
        cache_hit=bool(result.get("rag_cache_hit") or any(result.get("cache_hits", {}).values())),
        cost_saved=f"${float(result.get('cost_saved_usd', 0.0)):.2f}",
        metadata=ResponseMetadata(
            route=result.get("intent", "rag"),
            restructure_method=method_label,
            retrieved_chunks=chunk_previews,
            reflection_iterations=int(result.get("reflection_iterations") or 0),
            refined_question=result.get("refined_question"),
        ),
    )


@router.post("/query/sql/execute")
async def execute_sql(body: dict, user: User = Depends(get_current_user)) -> ChatResponse:
    query_id = body.get("query_id")
    approved = body.get("approved", False)
    if not query_id:
        raise HTTPException(status_code=400, detail="query_id required")

    config = {"configurable": {"thread_id": query_id}}
    result = graph.invoke(
        Command(resume={"approved": approved}),
        config=config,
    )

    # L7b + L9 for SQL path
    raw_answer = result.get("final_answer", "")
    out_allowed, redacted_answer, out_reason = moderate_and_redact(raw_answer)
    if not out_allowed:
        raise HTTPException(status_code=500, detail=f"output_blocked: {out_reason}")

    return ChatResponse(
        answer=redacted_answer,
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        metadata=ResponseMetadata(route="sql", validation_attempts=0),
    )
