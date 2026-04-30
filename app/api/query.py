"""Query endpoint backed by LangGraph orchestration."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command

from app.config import settings
from app.core.graph import graph
from app.middleware.auth import User, get_current_user
from app.middleware.rate_limiter import is_allowed_user
from app.models import ChatResponse, PendingSQLBlock, QueryRequest, ResponseMetadata
from app.security.token_budget import check_budget, consume_budget

router = APIRouter(tags=["query"])


@router.post("/query")
async def query(req: QueryRequest, user: User = Depends(get_current_user)) -> ChatResponse:
    allowed, _, _ = is_allowed_user(
        user.username,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    estimated_tokens = len(req.question.split()) + settings.reserved_output_tokens
    ok, remaining = check_budget(user.username, estimated_tokens)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"You have {remaining} tokens remaining today; this request estimated to use {estimated_tokens}.",
        )

    thread_id = str(uuid.uuid4())
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
            metadata=ResponseMetadata(route="sql"),
        )

    return ChatResponse(
        answer=result.get("final_answer", ""),
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        cache_hit=bool(result.get("rag_cache_hit") or any(result.get("cache_hits", {}).values())),
        cost_saved=f"${float(result.get('cost_saved_usd', 0.0)):.2f}",
        metadata=ResponseMetadata(route=result.get("intent", "rag")),
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

    return ChatResponse(
        answer=result.get("final_answer", ""),
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        metadata=ResponseMetadata(route="sql", validation_attempts=0),
    )
