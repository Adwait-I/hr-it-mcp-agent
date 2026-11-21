"""
src/ingest.py
─────────────
Chunk and embed both policy markdown files into a persistent ChromaDB
collection named `company_policies`.

Usage:
    python -m src.ingest
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from dotenv import load_dotenv
from google import genai

load_dotenv()

POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"
CHROMA_PATH = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "company_policies"
EMBEDDING_MODEL = "models/gemini-embedding-001"


# ---------------------------------------------------------------------------
# Custom embedding function using modern google-genai SDK
# ---------------------------------------------------------------------------

class GeminiEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-compatible embedding function using google-genai >= 1.0."""

    def __init__(self, api_key: str, model: str = EMBEDDING_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def __call__(self, input: Documents) -> Embeddings:
        result = self._client.models.embed_content(
            model=self._model,
            contents=list(input),
        )
        return [e.values for e in result.embeddings]


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def _chunk_markdown(text: str, source: str) -> list[dict]:
    """
    Split a markdown file on level-2 headings (## …).
    Returns a list of dicts with keys: id, text, source, section.
    """
    parts = re.split(r"(?m)^(## .+)$", text)
    chunks: list[dict] = []

    preamble = parts[0].strip()
    if preamble:
        chunks.append({
            "id": f"{source}::preamble",
            "text": preamble,
            "source": source,
            "section": "Introduction",
        })

    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].lstrip("# ").strip()
        body = parts[i + 1].strip()
        combined = f"{parts[i]}\n\n{body}"
        chunk_id = f"{source}::{heading.replace(' ', '_')}"
        chunks.append({
            "id": chunk_id,
            "text": combined,
            "source": source,
            "section": heading,
        })

    return chunks


# ---------------------------------------------------------------------------
# Main ingestion routine
# ---------------------------------------------------------------------------

def ingest_policies() -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit("❌  GEMINI_API_KEY is not set in .env — cannot create embeddings.")

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embed_fn = GeminiEmbeddingFunction(api_key=api_key)

    # (Re-)create collection so re-runs are idempotent
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"🗑️   Deleted existing collection '{COLLECTION_NAME}'.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"✅  Created collection '{COLLECTION_NAME}'.")

    all_chunks: list[dict] = []
    for md_file in sorted(POLICIES_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks = _chunk_markdown(text, source=md_file.name)
        all_chunks.extend(chunks)
        print(f"📄  {md_file.name}: {len(chunks)} chunk(s)")

    if not all_chunks:
        sys.exit("❌  No markdown files found in data/policies/.")

    collection.add(
        ids=[c["id"] for c in all_chunks],
        documents=[c["text"] for c in all_chunks],
        metadatas=[{"source": c["source"], "section": c["section"]} for c in all_chunks],
    )
    print(f"\n🎉  Ingested {len(all_chunks)} chunks into '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    ingest_policies()
