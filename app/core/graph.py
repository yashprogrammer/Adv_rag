"""LangGraph build function — minimal skeleton for Issue #4."""

import psycopg2
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.core.state import GraphState
from app.security.output_validator import validate_with_retry
from app.security.spotlighting import build_spotlighted_context
from app.security.system_prompt import build_system_prompt
from app.services.llm_service import generate


def route_intent(state: GraphState) -> GraphState:
    """Stub intent router — always returns 'rag' in Phase 1."""
    return {"intent": "rag"}


def generate_answer(state: GraphState) -> GraphState:
    """Generate an answer using the hardened system prompt + spotlighted context."""
    system = build_system_prompt()
    chunks = state.get("retrieved_chunks", [])
    spotlighted = build_spotlighted_context(chunks)
    user_msg = f"{spotlighted}\n\nQuestion: {state['question']}"

    result = generate(system, user_msg)
    raw = result["text"]

    def _retry_llm(prompt: str, error: str) -> str:
        retry_result = generate(system, prompt)
        return retry_result["text"]

    validated = validate_with_retry(raw, llm_fn=_retry_llm)
    return {
        "raw_answer": raw,
        "final_answer": validated.answer,
        "sources": validated.sources,
        "confidence": validated.confidence,
    }


def finalize(state: GraphState) -> GraphState:
    """Terminal node — no-op, answer already in state."""
    return {}


def _get_checkpointer():
    conn = psycopg2.connect(settings.database_url)
    return PostgresSaver(conn=conn)


def build_graph():
    """Build and compile the LangGraph with Postgres checkpointer."""
    builder = StateGraph(GraphState)
    builder.add_node("route_intent", route_intent)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "route_intent")
    builder.add_edge("route_intent", "generate_answer")
    builder.add_edge("generate_answer", "finalize")
    builder.add_edge("finalize", END)

    checkpointer = _get_checkpointer()
    return builder.compile(checkpointer=checkpointer)


# Module-level compiled graph (lazy import safe)
graph = build_graph()
