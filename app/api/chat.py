"""Stub chat endpoint for exercising rate limit + token budget middleware."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import settings
from app.middleware.auth import User, get_current_user
from app.middleware.rate_limiter import is_allowed_user
from app.security.token_budget import check_budget, consume_budget

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: Request, body: dict, user: User = Depends(get_current_user)) -> dict:
    # Per-user rate limit
    allowed, _, _ = is_allowed_user(
        user.username,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Token budget check (stub estimate = 10 tokens)
    estimated_tokens = 10 + settings.reserved_output_tokens
    ok, remaining = check_budget(user.username, estimated_tokens)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"You have {remaining} tokens remaining today; this request estimated to use {estimated_tokens}.",
        )

    # Stub generate
    answer = "stub"
    consume_budget(user.username, estimated_tokens)

    return {
        "answer": answer,
        "sources": [],
        "confidence": 0.5,
        "cache_hit": False,
        "cost_saved": "$0.00",
    }
