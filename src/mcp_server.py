"""
src/mcp_server.py
─────────────────
FastMCP server exposing read-only PostgreSQL tools over stdio.

Start-up (called automatically by agent.py via subprocess):
    python -m src.mcp_server
"""

from __future__ import annotations

import json
import os
import re

import psycopg2
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env")

# Mutating SQL keywords that are never permitted
_BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|REPLACE|MERGE)\b",
    re.IGNORECASE,
)

mcp = FastMCP(name="hr-it-postgres")


def _get_connection() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_session(readonly=True, autocommit=True)
    return conn


@mcp.tool()
def list_tables() -> str:
    """
    Return the schema (table names and column details) for all tables
    in the public schema of the connected PostgreSQL database.
    """
    sql = """
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        schema: dict[str, list[dict]] = {}
        for table, column, dtype, nullable in rows:
            schema.setdefault(table, []).append(
                {"column": column, "type": dtype, "nullable": nullable}
            )
        return json.dumps(schema, indent=2)
    finally:
        conn.close()


@mcp.tool()
def query_readonly_sql(sql: str) -> str:
    """
    Execute a read-only SELECT query against the PostgreSQL database and
    return the results as a JSON-encoded list of row objects.

    Only SELECT statements are permitted. Mutating operations
    (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, GRANT, etc.) are blocked.

    Args:
        sql: A valid SELECT statement to execute.
    """
    # --- Security validation ---
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT statements are permitted."})

    if _BLOCKED_KEYWORDS.search(stripped):
        return json.dumps(
            {
                "error": (
                    "Query blocked: contains a mutating or administrative SQL keyword "
                    "(INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, GRANT, etc.)."
                )
            }
        )

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(stripped)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
        result = [dict(zip(columns, row)) for row in rows]
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
