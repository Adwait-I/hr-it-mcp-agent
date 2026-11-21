"""
src/agent.py
─────────────
HR & IT Helpdesk AI Agent.

Capabilities:
  • RAG over company policy documents (ChromaDB)
  • Read-only SQL queries via PostgreSQL MCP server (FastMCP/stdio)
  • Input guardrails  (prompt-injection + out-of-scope detection)
  • Output guardrails (PII redaction)

Public API:
    ask_agent(user_query: str) -> str
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.guardrails import check_input_guardrails, redact_pii
from src.ingest import GeminiEmbeddingFunction

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHROMA_PATH = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "company_policies"
MCP_SERVER_MODULE = "src.mcp_server"   # run with: python -m src.mcp_server
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "models/gemini-3.1-flash-lite")

_SYSTEM_PROMPT = """\
You are the HR & IT Helpdesk AI Assistant for a corporate organisation.

Your role:
  - Answer questions about HR policies (leave, hybrid work) and IT policies
    (passwords, MFA, VPN, device management).
  - Look up employee-specific information (leave balances, assigned IT assets)
    from the company database using the provided SQL tools.
  - Always cite the exact source filename and section when answering policy questions,
    e.g. "[Source: hr_leave_policy.md | Annual Leave Accrual]".
  - If you cannot find an answer in the available tools or policies, clearly say so —
    do NOT hallucinate facts.
  - Keep responses concise, professional, and factual.

Constraints:
  - Only use the provided tools; do not make up data.
  - Never reveal raw SSN values, full phone numbers, or email addresses in your answers.
  - If asked for sensitive PII, acknowledge the request but decline to surface the raw value.
"""

# ---------------------------------------------------------------------------
# Gemini client (singleton)
# ---------------------------------------------------------------------------

_genai_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            sys.exit("❌  GEMINI_API_KEY is not set in .env")
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client


# ---------------------------------------------------------------------------
# ChromaDB / RAG
# ---------------------------------------------------------------------------

_chroma_collection: chromadb.Collection | None = None


def _get_chroma_collection() -> chromadb.Collection:
    global _chroma_collection
    if _chroma_collection is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        embed_fn = GeminiEmbeddingFunction(api_key=api_key, model="models/gemini-embedding-001")
        _chroma_collection = client.get_collection(
            name=COLLECTION_NAME, embedding_function=embed_fn
        )
    return _chroma_collection


def search_policies_rag(query: str, n_results: int = 3) -> str:
    """
    Query ChromaDB for the most relevant policy excerpts.
    Returns a formatted string with citations for each result.
    """
    try:
        collection = _get_chroma_collection()
        results = collection.query(query_texts=[query], n_results=n_results)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        if not documents:
            return "No relevant policy excerpts found."
        parts: list[str] = []
        for doc, meta in zip(documents, metadatas):
            source = meta.get("source", "unknown")
            section = meta.get("section", "unknown")
            parts.append(f"[Source: {source} | {section}]\n{doc}")
        return "\n\n---\n\n".join(parts)
    except Exception as exc:
        return f"RAG search error: {exc}"


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

async def _call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Spin up the MCP server subprocess and call a single tool."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", MCP_SERVER_MODULE],
        env={**os.environ},
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            # result.content is a list of content objects
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
                else:
                    texts.append(str(item))
            return "\n".join(texts)


def _mcp_list_tables() -> str:
    return asyncio.run(_call_mcp_tool("list_tables", {}))


def _mcp_query_sql(sql: str) -> str:
    return asyncio.run(_call_mcp_tool("query_readonly_sql", {"sql": sql}))


# ---------------------------------------------------------------------------
# Gemini tool definitions
# ---------------------------------------------------------------------------

_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_policies_rag",
                description=(
                    "Search the company policy documents (HR leave policy, IT security policy) "
                    "using semantic vector search. Use this to answer any question about policies, "
                    "rules, procedures, or guidelines. Always cite the [Source] in your answer."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="A natural-language question or keyword to search for.",
                        )
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="list_tables",
                description=(
                    "List all tables and their column schemas in the HR/IT PostgreSQL database. "
                    "Call this first to understand what data is available before writing SQL."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="query_readonly_sql",
                description=(
                    "Execute a read-only SELECT query against the HR/IT PostgreSQL database. "
                    "Only SELECT statements are allowed. Use this to look up employee leave balances, "
                    "assigned IT assets, and other employee-specific data."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "sql": types.Schema(
                            type=types.Type.STRING,
                            description="A valid SQL SELECT statement.",
                        )
                    },
                    required=["sql"],
                ),
            ),
        ]
    )
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, args: dict) -> str:
    if name == "search_policies_rag":
        return search_policies_rag(args.get("query", ""))
    elif name == "list_tables":
        return _mcp_list_tables()
    elif name == "query_readonly_sql":
        return _mcp_query_sql(args.get("sql", ""))
    else:
        return f"Unknown tool: {name}"


# ---------------------------------------------------------------------------
# Main agent entrypoint
# ---------------------------------------------------------------------------

def ask_agent(user_query: str) -> str:
    """
    Process a user query through the full pipeline:
      1. Input guardrails
      2. Gemini agentic loop with RAG + MCP tools
      3. Output guardrails (PII redaction)

    Returns the agent's response as a plain string.
    """
    # --- Step 1: Input guardrails ---
    allowed, refusal = check_input_guardrails(user_query)
    if not allowed:
        return refusal

    # --- Step 2: Gemini agentic loop ---
    client = _get_genai_client()

    messages: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=user_query)])
    ]

    max_turns = 8
    for _ in range(max_turns):
        response = None
        for attempt in range(5):
            try:
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        tools=_TOOLS,
                        temperature=0.1,
                    ),
                )
                break
            except Exception as exc:
                err_msg = str(exc)
                if ("429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "503" in err_msg) and attempt < 4:
                    wait_time = 4 * (attempt + 1)
                    time.sleep(wait_time)
                    continue
                final_text = f"I encountered an error generating a response: {exc}"
                break
        if response is None:
            break

        candidate = response.candidates[0]
        content = candidate.content

        # Guard: some finish reasons produce empty content (SAFETY, RECITATION, etc.)
        if not content or not content.parts:
            finish = getattr(candidate, "finish_reason", None)
            final_text = (
                f"I was unable to provide a response to that query "
                f"(finish reason: {finish})."
            )
            break

        # Collect all function calls in this turn (skip thought/None parts)
        function_calls = [
            part.function_call
            for part in content.parts
            if getattr(part, "function_call", None) is not None
        ]

        if not function_calls:
            # Model produced a final text response — collect non-None, non-empty text parts
            # (skip thought parts which have text=None in thinking models)
            text_parts = [
                part.text
                for part in content.parts
                if getattr(part, "text", None) and not getattr(part, "thought", False)
            ]
            final_text = "\n".join(text_parts).strip() or "I could not generate a response for that query."
            break

        # Append the model's turn
        messages.append(content)

        # Execute all tool calls and collect results
        tool_response_parts: list[types.Part] = []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            tool_result = _dispatch_tool(fc.name, args)
            tool_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": tool_result},
                    )
                )
            )

        messages.append(
            types.Content(role="user", parts=tool_response_parts)
        )
    else:
        final_text = "I was unable to generate a complete response after multiple reasoning steps."

    # --- Step 3: Output guardrails (PII redaction) ---
    return redact_pii(final_text)


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(ask_agent(query))
    else:
        print("\n" + "=" * 55)
        print("  🏢 HR & IT Helpdesk AI Agent — Interactive Chat")
        print("  Type your question and press Enter.")
        print("  Type 'exit' or 'quit' to leave.")
        print("=" * 55 + "\n")
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    print("Goodbye!")
                    break
                answer = ask_agent(user_input)
                print(f"\nAgent:\n{answer}\n")
                print("-" * 55 + "\n")
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break
