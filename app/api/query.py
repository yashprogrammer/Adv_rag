"""Query endpoint backed by LangGraph orchestration."""

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.core.graph import graph
from app.middleware.auth import User, get_current_user
from app.middleware.rate_limiter import is_allowed_user
from app.models import ChatResponse, QueryRequest, ResponseMetadata
from app.security.token_budget import check_budget, consume_budget

router = APIRouter(tags=["query"])


@router.post("/query")
async def query(req: QueryRequest, user: User = Depends(get_current_user)) -> ChatResponse:
    # Per-user rate limit
    allowed, _, _ = is_allowed_user(
        user.username,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Token budget check
    estimated_tokens = len(req.question.split()) + settings.reserved_output_tokens
    ok, remaining = check_budget(user.username, estimated_tokens)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"You have {remaining} tokens remaining today; this request estimated to use {estimated_tokens}.",
        )

    thread_id = "test-thread"  # TODO: use UUID in production
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(
        {
            "question": req.question,
            "user_id": user.username,
            "flags": req.model_dump(),
            "retrieved_chunks": [],
            "sources": [],
            "cache_hits": {},
            "cost_saved_usd": 0.0,
        },
        config=config,
    )

    consume_budget(user.username, estimated_tokens)

    return ChatResponse(
        answer=result.get("final_answer", ""),
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        metadata=ResponseMetadata(route=result.get("intent", "rag")),
    )
