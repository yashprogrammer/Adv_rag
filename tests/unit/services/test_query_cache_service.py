"""Unit tests for query cache service."""

from app.services.query_cache_service import QueryCacheService


def test_key_helpers_stable_and_normalized() -> None:
    svc = QueryCacheService()

    intent_a = svc.intent_key("  Where Is My Order? ")
    intent_b = svc.intent_key("where is my order?")
    assert intent_a == intent_b
    assert intent_a.startswith("intent:")

    sql_a = svc.sql_result_key("SELECT   *  FROM users")
    sql_b = svc.sql_result_key(" select * from users ")
    assert sql_a == sql_b
    assert sql_a.startswith("sql_result:")


def test_memory_fallback_get_set_and_stats(monkeypatch) -> None:
    monkeypatch.setattr("app.services.query_cache_service.settings.upstash_redis_url", "")
    monkeypatch.setattr("app.services.query_cache_service.settings.upstash_redis_token", "")

    svc = QueryCacheService()
    assert svc.get_intent("x") is None

    svc.set_intent("x", "rag")
    assert svc.get_intent("x") == "rag"

    stats = svc.stats()
    assert stats["intent"]["misses"] == 1
    assert stats["intent"]["hits"] == 1
    assert stats["intent"]["sets"] == 1


def test_ttls_used_for_each_tier(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    class FakeRedis:
        def set(self, key: str, value: str, ex: int) -> None:
            calls.append((key, ex))

        def get(self, _key: str):
            return None

    monkeypatch.setattr(QueryCacheService, "_build_redis_client", lambda _self: FakeRedis())
    monkeypatch.setattr("app.services.query_cache_service.settings.cache_ttl_intent", 11)
    monkeypatch.setattr("app.services.query_cache_service.settings.cache_ttl_rag", 22)
    monkeypatch.setattr("app.services.query_cache_service.settings.cache_ttl_sql_gen", 33)
    monkeypatch.setattr("app.services.query_cache_service.settings.cache_ttl_sql_result", 44)

    svc = QueryCacheService()
    svc.set_intent("q", "intent")
    svc.set_rag_answer("q", {"answer": "ok"})
    svc.set_sql_generation("q", "select 1")
    svc.set_sql_result("select 1", [{"x": 1}])

    assert [ttl for _key, ttl in calls] == [11, 22, 33, 44]


def test_redis_error_does_not_raise_on_set(monkeypatch) -> None:
    class BrokenRedis:
        def set(self, _key: str, _value: str, ex: int) -> None:
            raise RuntimeError("boom")

        def get(self, _key: str):
            return None

    monkeypatch.setattr(QueryCacheService, "_build_redis_client", lambda _self: BrokenRedis())
    svc = QueryCacheService()

    svc.set_sql_generation("q", "select 1")
    assert svc.get_sql_generation("q") == "select 1"


def test_embedding_get_set_and_stats(monkeypatch) -> None:
    monkeypatch.setattr("app.services.query_cache_service.settings.upstash_redis_url", "")
    monkeypatch.setattr("app.services.query_cache_service.settings.upstash_redis_token", "")
    monkeypatch.setattr("app.services.query_cache_service.settings.cache_ttl_embeddings", 99)

    svc = QueryCacheService()
    assert svc.get_embedding("hello world") is None

    svc.set_embedding("hello world", [0.1, 0.2, 0.3])
    assert svc.get_embedding("hello world") == [0.1, 0.2, 0.3]

    stats = svc.stats()
    assert stats["embedding"]["misses"] == 1
    assert stats["embedding"]["hits"] == 1
    assert stats["embedding"]["sets"] == 1
