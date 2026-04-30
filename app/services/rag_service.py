"""Naive RAG service — embed, search, spotlight, generate, validate."""

from app.models import ChatResponse
from app.security.output_validator import validate_with_retry
from app.security.spotlighting import build_spotlighted_context
from app.security.system_prompt import build_system_prompt
from app.services.embedding_service import embed_texts
from app.services.llm_service import generate
from app.services.vector_store import search


def run_rag(question: str, top_k: int = 5) -> ChatResponse:
    """Run the naive RAG pipeline.

    1. Embed the question
    2. Search Qdrant for top-k chunks
    3. Spotlight chunks
    4. Generate answer with LLM
    5. Validate output schema
    """
    # 1. Embed query
    embeddings = embed_texts([question])
    query_embedding = embeddings[0]

    # 2. Retrieve
    chunks = search(query_embedding, top_k=top_k)

    # 3. Spotlight
    spotlighted = build_spotlighted_context(chunks)

    # 4. Generate
    system = build_system_prompt()
    user_msg = f"{spotlighted}\n\nQuestion: {question}"
    result = generate(system, user_msg)
    raw = result["text"]

    # 5. Validate
    def _retry_llm(prompt: str, error: str) -> str:
        return generate(system, prompt)["text"]

    validated = validate_with_retry(raw, llm_fn=_retry_llm)
    return validated
