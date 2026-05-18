"""POST /query — Lesson 9: full security pipeline around run_rag.

L8 had a bare /query endpoint that called run_rag directly. L9 wraps it
with defense-in-depth:

  1. Rate limit (per-user, sliding window)
  2. Token budget (per-user, per-day)
  3. Input restructuring (truncate or summarize if too long)
  4. llm-guard input scan (prompt injection, ban-topics, toxicity)
  5. Input content moderation + PII redaction
  6. run_rag
  7. Output content moderation + PII redaction
  8. Consume the token budget

If any defensive layer fires, the endpoint returns the appropriate
HTTP error (422/400/429) and the model is never invoked — cheap
attacks die before they cost tokens.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.middleware.auth import User, get_current_user
from app.middleware.rate_limiter import is_allowed_user
from app.models import ChatResponse, QueryRequest
from app.security.content_moderation import moderate_and_redact
from app.security.input_guard import check_input_safe
from app.security.input_restructuring import count_tokens, restructure_input
from app.security.token_budget import check_budget, consume_budget
from app.services.rag_service import run_rag

router = APIRouter(tags=["query"])


def _estimate_tokens(question: str) -> int:
    return count_tokens(question) + settings.reserved_output_tokens


@router.post("/query", response_model=ChatResponse)
async def query(
    body: QueryRequest,
    user: User = Depends(get_current_user),
) -> ChatResponse:
    # Layer 3: per-user sliding-window rate limit
    allowed, _, _ = is_allowed_user(
        user.username,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Layer 3 (token budget): per-user per-day
    estimated = _estimate_tokens(body.question)
    ok, remaining = check_budget(user.username, estimated)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You have {remaining} tokens remaining today; "
                f"this request estimated to use {estimated}."
            ),
        )

    # Layer 1 (input restructuring): truncate/summarize if too long
    restructured, _method = restructure_input(body.question)

    # Layer 2 (LLM-Guard input scan): injection / ban-topic / toxicity
    guard_allowed, guard_reason = check_input_safe(restructured)
    if not guard_allowed:
        raise HTTPException(status_code=400, detail=f"injection_blocked: {guard_reason}")

    # Layer 4 (content moderation in): PII redaction + toxicity
    mod_allowed, moderated_in, mod_reason = moderate_and_redact(restructured)
    if not mod_allowed:
        raise HTTPException(status_code=400, detail=f"content_blocked: {mod_reason}")

    # === Call the RAG pipeline ===
    response = run_rag(
        moderated_in,
        flags={
            "top_k": body.top_k,
            "search_mode": body.search_mode,
            "enable_rerank": body.enable_rerank,
            "enable_hyde": body.enable_hyde,
            "enable_crag": body.enable_crag,
            "enable_self_reflective": body.enable_self_reflective,
        },
    )

    # Layer 6 (content moderation out): redact PII before returning
    out_allowed, redacted, _ = moderate_and_redact(response.answer)
    if not out_allowed:
        raise HTTPException(status_code=500, detail="output_blocked")
    response.answer = redacted

    # Consume the budget (only when the call actually succeeded)
    consume_budget(user.username, estimated)

    return response
