"""LangGraph build function — Phase 1 skeleton with SQL interrupt path."""

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.config import settings
from app.core.state import GraphState
from app.services.rag_service import run_rag
from app.services.router_service import classify_intent
from app.services.sql_service import SQLService

sql_service = SQLService()


def route_intent(state: GraphState) -> dict:
    """LLM-based intent router for sql/rag/hybrid."""
    intent = classify_intent(state["question"])
    return {"intent": intent}


def generate_sql_node(state: GraphState) -> dict:
    """Generate SQL using the LLM."""
    result = sql_service.generate_sql(state["question"])
    return {
        "generated_sql": result["sql"],
        "sql_explanation": result["explanation"],
    }


def request_sql_approval(state: GraphState) -> dict:
    """Pause for human approval via interrupt().

    When LangGraph replays this node on resume, interrupt() returns the
    resume value immediately — no expensive operations are repeated.
    """
    approval = interrupt({
        "type": "sql_approval_required",
        "sql": state["generated_sql"],
        "explanation": state["sql_explanation"],
    })
    return {"sql_approved": approval.get("approved", False)}


def execute_sql(state: GraphState) -> dict:
    """Execute approved SQL and store results."""
    if not state.get("sql_approved"):
        return {"sql_rows": [], "final_answer": "SQL query was not approved."}

    sql = state.get("generated_sql", "")
    try:
        rows = sql_service.execute_sql(sql)
        return {"sql_rows": rows}
    except Exception as exc:
        return {"sql_rows": [], "final_answer": f"SQL execution failed: {exc}"}


def generate_answer(state: GraphState) -> dict:
    """Generate an answer using RAG or SQL results."""
    intent = state.get("intent", "rag")

    if intent == "sql":
        rows = state.get("sql_rows", [])
        if not rows:
            return {
                "final_answer": state.get("final_answer", "No results."),
                "sources": ["database query"],
                "confidence": 0.9,
            }
        # Format rows as markdown table
        import json
        answer = f"Query results:\n```\n{json.dumps(rows, indent=2)}\n```"
        return {
            "final_answer": answer,
            "sources": ["database query"],
            "confidence": 0.9,
        }

    # RAG path
    response = run_rag(state["question"], flags=state.get("flags", {}))
    return {
        "final_answer": response.answer,
        "sources": response.sources,
        "confidence": response.confidence,
        "rag_cache_hit": response.cache_hit,
        "cache_hits": {"rag_answer": response.cache_hit},
    }


def finalize(state: GraphState) -> dict:
    """Terminal node — no-op."""
    return {}


def _get_checkpointer():
    conn = psycopg.connect(settings.database_url, autocommit=True)
    saver = PostgresSaver(conn=conn)
    saver.setup()
    return saver


def build_graph():
    """Build and compile the LangGraph with Postgres checkpointer."""
    builder = StateGraph(GraphState)
    builder.add_node("route_intent", route_intent)
    builder.add_node("generate_sql_node", generate_sql_node)
    builder.add_node("request_sql_approval", request_sql_approval)
    builder.add_node("execute_sql", execute_sql)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "route_intent")
    builder.add_conditional_edges(
        "route_intent",
        lambda s: s.get("intent", "rag"),
        {"sql": "generate_sql_node", "rag": "generate_answer", "hybrid": "generate_answer"},
    )
    builder.add_edge("generate_sql_node", "request_sql_approval")
    builder.add_edge("request_sql_approval", "execute_sql")
    builder.add_edge("execute_sql", "generate_answer")
    builder.add_edge("generate_answer", "finalize")
    builder.add_edge("finalize", END)

    checkpointer = _get_checkpointer()
    return builder.compile(checkpointer=checkpointer)


# Module-level compiled graph
graph = build_graph()
