"""Unit tests for per-user daily token budget."""

from unittest.mock import MagicMock, patch

from app.security.token_budget import TokenBudget


class TestTokenBudget:
    def test_check_budget_allows_when_under_limit(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = "1000"  # used 1k of 100k

        budget = TokenBudget(max_tokens=100_000)
        with patch("app.security.token_budget.get_redis_client", return_value=mock_redis):
            ok, remaining = budget.check_budget("alice", estimated_tokens=5000)

        assert ok is True
        assert remaining == 99_000

    def test_check_budget_rejects_when_over_limit(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = "99_000"  # used 99k of 100k

        budget = TokenBudget(max_tokens=100_000)
        with patch("app.security.token_budget.get_redis_client", return_value=mock_redis):
            ok, remaining = budget.check_budget("alice", estimated_tokens=5000)

        assert ok is False
        assert remaining == 1_000

    def test_check_budget_with_no_prior_usage(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # no usage yet

        budget = TokenBudget(max_tokens=100_000)
        with patch("app.security.token_budget.get_redis_client", return_value=mock_redis):
            ok, remaining = budget.check_budget("alice", estimated_tokens=5000)

        assert ok is True
        assert remaining == 100_000

    def test_consume_increments_counter(self) -> None:
        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 5000
        mock_redis.ttl.return_value = -1

        budget = TokenBudget(max_tokens=100_000)
        with patch("app.security.token_budget.get_redis_client", return_value=mock_redis):
            result = budget.consume("alice", actual_tokens=5000)

        assert result["used"] == 5000
        assert result["limit"] == 100_000
        assert result["remaining"] == 95_000
        mock_redis.incrby.assert_called_once()

    def test_consume_sets_ttl_on_first_use(self) -> None:
        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 5000
        mock_redis.ttl.return_value = -1  # no TTL set yet

        budget = TokenBudget(max_tokens=100_000)
        with patch("app.security.token_budget.get_redis_client", return_value=mock_redis):
            budget.consume("alice", actual_tokens=5000)

        mock_redis.expire.assert_called_once()
        # TTL should be set to seconds-until-midnight (roughly)
        ttl_arg = mock_redis.expire.call_args[0][1]
        assert 0 < ttl_arg <= 86_400

    def test_consume_does_not_reset_ttl_if_exists(self) -> None:
        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 5000
        mock_redis.ttl.return_value = 3600  # already has TTL

        budget = TokenBudget(max_tokens=100_000)
        with patch("app.security.token_budget.get_redis_client", return_value=mock_redis):
            budget.consume("alice", actual_tokens=5000)

        mock_redis.expire.assert_not_called()
