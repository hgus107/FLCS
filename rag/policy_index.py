# RAG: shared policy search. Loads the pre-built index of policy chunks, embeds an
# incoming question with the same small local model, and returns the closest few
# paragraphs. Every MCP server imports this so all agents quote the same rulebook.

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

INDEX = Path("data/policy_index.json")

_data = json.loads(INDEX.read_text())
_chunks = _data["chunks"]

# REQUIREMENT: normalise once at load so each search is a single matrix multiply
# rather than a per-row division.
_matrix = np.array([c["vector"] for c in _chunks], dtype=np.float32)
_matrix /= np.linalg.norm(_matrix, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def _model():
    # REQUIREMENT: loaded on first search, not at import, so starting an MCP server
    # that never searches costs nothing.
    return TextEmbedding(model_name=_data["model"])


def search(query: str, area: str | None = None, k: int = 3):
    """Return the k policy paragraphs closest in meaning to the query.
    Pass area to restrict to one rulebook: fraud, lending, compliance or support."""
    vector = np.array(next(iter(_model().embed([query]))), dtype=np.float32)
    vector /= np.linalg.norm(vector)

    scores = _matrix @ vector

    order = np.argsort(scores)[::-1]

    results = []
    for i in order:
        chunk = _chunks[i]
        if area and chunk["area"] != area:
            continue

        results.append(
            {
                "document": chunk["document"],
                "section": chunk["heading"],
                "text": chunk["text"],
                "relevance": round(float(scores[i]), 3),
            }
        )

        if len(results) == k:
            break

    return results