"""OpenAI embedding service — thin adapter."""

from openai import OpenAI

from app.config import settings

openai_client = OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed a list of texts using OpenAI embeddings.

    Returns:
        List of embedding vectors in the same order as input texts.
    """
    if not texts:
        return []
    if model is None:
        model = settings.embedding_model

    response = openai_client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in response.data]
