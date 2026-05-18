"""Unit tests for sparse vector service."""

from app.models import RetrievedChunk
from app.services.sparse_vector_service import SparseVectorIndex, fuse_rrf


def test_sparse_vector_index_fit_and_search() -> None:
    docs = [
        {"text": "The quick brown fox jumps over the lazy dog", "source": "doc1", "id": "1"},
        {"text": "A fast brown fox leaps over a sleepy dog", "source": "doc2", "id": "2"},
        {"text": "The car is red and very fast", "source": "doc3", "id": "3"},
    ]
    index = SparseVectorIndex()
    index.fit(docs)
    results = index.search("fast brown fox", top_k=2)
    assert len(results) == 2
    texts = [r.text for r in results]
    assert any("fox" in t for t in texts)


def test_empty_index_returns_empty() -> None:
    index = SparseVectorIndex()
    assert index.search("query") == []
    index.fit([])
    assert index.search("query") == []


def test_fuse_rrf_ordering() -> None:
    list1 = [
        RetrievedChunk(text="A", source="s1", score=0.9),
        RetrievedChunk(text="B", source="s1", score=0.8),
    ]
    list2 = [
        RetrievedChunk(text="B", source="s2", score=0.95),
        RetrievedChunk(text="C", source="s2", score=0.85),
        RetrievedChunk(text="A", source="s2", score=0.7),
    ]
    fused = fuse_rrf([list1, list2], rrf_k=60)
    texts = [c.text for c in fused]
    assert texts[0] == "B"
    assert "A" in texts
    assert "C" in texts
    assert texts.index("A") < texts.index("C")
