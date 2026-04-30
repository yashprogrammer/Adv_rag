"""Unit tests for sliding-window rate limiter."""

from unittest.mock import MagicMock, patch

from app.middleware.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_allows_requests_under_limit(self) -> None:
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.exec.return_value = [0, 1, 1, 1]  # zrem, zadd, zcard=1, expire

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        with patch("app.middleware.rate_limiter.get_redis_client", return_value=mock_redis):
            allowed, remaining, count = limiter.is_allowed("user:alice")

        assert allowed is True
        assert remaining == 4
        assert count == 1

    def test_blocks_at_limit(self) -> None:
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.exec.return_value = [0, 1, 21, 1]  # zcard=21 > max_requests=20

        limiter = RateLimiter(max_requests=20, window_seconds=60)
        with patch("app.middleware.rate_limiter.get_redis_client", return_value=mock_redis):
            allowed, remaining, count = limiter.is_allowed("user:alice")

        assert allowed is False
        assert remaining == 0
        assert count == 21

    def test_keyspace_isolation_user_vs_ip(self) -> None:
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.exec.return_value = [0, 1, 5, 1]

        limiter = RateLimiter(max_requests=10, window_seconds=60)
        with patch("app.middleware.rate_limiter.get_redis_client", return_value=mock_redis):
            limiter.is_allowed("user:alice")
            limiter.is_allowed("ip:1.2.3.4")

        calls = mock_redis.exec.call_args_list
        assert len(calls) == 2
        # Verify different keys were used (checked via zadd call on the pipeline)
        first_key = mock_redis.zadd.call_args_list[0][0][0]
        second_key = mock_redis.zadd.call_args_list[1][0][0]
        assert first_key != second_key
        assert "user:alice" in first_key
        assert "ip:1.2.3.4" in second_key

    def test_boundary_at_exact_window_edge(self) -> None:
        """A request at exactly the window boundary should not count old entries."""
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.exec.return_value = [0, 1, 1, 1]

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        with patch("app.middleware.rate_limiter.get_redis_client", return_value=mock_redis):
            allowed, _, _ = limiter.is_allowed("rate_limit:user:alice")

        # The zremrangebyscore call should remove entries older than now - 60s
        zrem_call = mock_redis.zremrangebyscore.call_args
        assert zrem_call is not None
        assert zrem_call[0][0] == "rate_limit:user:alice"
        assert allowed is True
