# DATA PREP: one-off script. Splits the four policy documents into chunks, turns each
# chunk into a vector with a small local model, and saves both to a single JSON file.
# The MCP servers load that file and only ever embed the incoming question, which is
# what keeps a policy search fast.

import json
import re
from pathlib import Path

from fastembed import TextEmbedding

POLICY_DIR = Path("data/policies")
OUT = Path("data/policy_index.json")
MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# REQUIREMENT: which agent may see which document. Support answers questions about
# any of them; the specialists see only their own rulebook.
AREA = {
    "fraud_policy.md": "fraud",
    "lending_policy.md": "lending",
    "compliance_policy.md": "compliance",
    "support_policy.md": "support",
}


def chunk(markdown: str):
    """Split on section headings, then on blank lines, keeping the heading with each
    piece so a retrieved chunk still says what it is about."""
    chunks = []

    for section in re.split(r"\n(?=## )", markdown):
        lines = section.strip().split("\n")
        if not lines:
            continue

        heading = lines[0].lstrip("# ").strip()
        body = "\n".join(lines[1:]).strip()

        for para in re.split(r"\n\s*\n", body):
            para = para.strip()
            # Skip fragments too short to carry meaning on their own.
            if len(para.split()) < 12:
                continue
            chunks.append({"heading": heading, "text": para})

    return chunks


records = []

for path in sorted(POLICY_DIR.glob("*.md")):
    area = AREA.get(path.name, "general")
    markdown = path.read_text()

    for c in chunk(markdown):
        records.append(
            {
                "area": area,
                "document": path.name,
                "heading": c["heading"],
                "text": c["text"],
            }
        )

print(f"{len(records)} chunks from {len(list(POLICY_DIR.glob('*.md')))} documents")
print("Loading the embedding model (first run downloads about 90MB)...")

model = TextEmbedding(model_name=MODEL)

# REQUIREMENT: prefix each chunk with its heading before embedding, so a paragraph
# about "lifting a block" still matches a question about card blocks.
texts = [f"{r['heading']}. {r['text']}" for r in records]
vectors = [v.tolist() for v in model.embed(texts)]

for r, v in zip(records, vectors):
    r["vector"] = v

OUT.write_text(json.dumps({"model": MODEL, "chunks": records}))
print(f"Wrote {OUT} — {len(records)} chunks, {len(vectors[0])} dimensions each")