"""Unit tests for SQL service."""

from unittest.mock import MagicMock, patch

from app.services.sql_service import SQLService, is_select_only


class TestIsSelectOnly:
    def test_select_passes(self) -> None:
        assert is_select_only("SELECT * FROM users") is True

    def test_insert_blocked(self) -> None:
        assert is_select_only("INSERT INTO users VALUES (1)") is False

    def test_update_blocked(self) -> None:
        assert is_select_only("UPDATE users SET name='x'") is False

    def test_delete_blocked(self) -> None:
        assert is_select_only("DELETE FROM users") is False

    def test_drop_blocked(self) -> None:
        assert is_select_only("DROP TABLE users") is False


class TestSQLService:
    @patch("app.services.sql_service.generate")
    def test_generate_sql_returns_sql_and_explanation(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {
            "text": '{"sql": "SELECT COUNT(*) FROM customers WHERE country = \'Germany\'", "explanation": "Count German customers"}',
            "usage": {},
        }
        service = SQLService()
        result = service.generate_sql("How many customers in Germany?")
        assert "sql" in result
        assert "explanation" in result
        assert "COUNT(*)" in result["sql"]

    def test_build_schema_context_non_empty(self) -> None:
        service = SQLService()
        ctx = service._build_schema_context()
        assert "customers" in ctx.lower() or "users" in ctx.lower()
