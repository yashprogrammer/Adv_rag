"""SQL service — lightweight Text2SQL using LLM with schema context."""

import json
import re

import psycopg2

from app.config import settings
from app.services.llm_service import generate


def is_select_only(sql: str) -> bool:
    """Return True if the SQL is a SELECT statement only."""
    cleaned = sql.strip().lower()
    # Must start with select
    if not cleaned.startswith("select"):
        return False
    # Must not contain dangerous keywords
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke"]
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", cleaned):
            return False
    return True


class SQLService:
    def __init__(self):
        self._schema_context: str | None = None

    def _build_schema_context(self) -> str:
        """Introspect information_schema.columns and cache the result."""
        if self._schema_context is not None:
            return self._schema_context

        conn = psycopg2.connect(settings.database_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        tables: dict[str, list[str]] = {}
        for table, col, dtype in rows:
            tables.setdefault(table, []).append(f"{col} ({dtype})")

        lines = ["Database schema:"]
        for table, cols in tables.items():
            lines.append(f"  {table}: {', '.join(cols)}")

        self._schema_context = "\n".join(lines)
        return self._schema_context

    def generate_sql(self, question: str) -> dict:
        """Generate SQL from a natural language question.

        Returns:
            dict with "sql" and "explanation" keys.
        """
        schema = self._build_schema_context()
        system = (
            "You are a SQL expert. Given a database schema and a question, "
            "generate a valid PostgreSQL SELECT query. Return JSON with keys: sql, explanation."
        )
        user = f"{schema}\n\nQuestion: {question}\n\nReturn only the JSON."
        result = generate(system, user, model=settings.vanna_model, temperature=settings.vanna_temperature)
        text = result["text"]

        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1]).strip()

        data = json.loads(text)
        return {
            "sql": data.get("sql", ""),
            "explanation": data.get("explanation", ""),
        }

    def execute_sql(self, sql: str) -> list[dict]:
        """Execute a SELECT query and return rows as dicts."""
        if not is_select_only(sql):
            raise ValueError("Only SELECT statements are allowed")

        conn = psycopg2.connect(settings.database_url)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return [dict(zip(columns, row, strict=True)) for row in rows]
