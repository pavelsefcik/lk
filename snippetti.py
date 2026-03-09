"""
Snippetti - Semantic bookmark search for folders and files
Uses Mistral's mistral-embed model for embeddings.

Usage:
    snippetti add "/Users/you/dev/libs" "GitHub Libraries" "Codebases from GitHub"
    snippetti search "react tutorials"
    snippetti list
"""

import json
import math
import os
import sys
from pathlib import Path

import tomli_w  # pip install tomli-w  (writes TOML)
import tomllib  # built-in from Python 3.11+
from mistralai import Mistral

# ── Configuration ────────────────────────────────────────────────────────────

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "YOUR_KEY_HERE")
SNIPPETS_FILE = Path("snippets.toml")  # human-readable snippet store
EMBEDDINGS_FILE = Path("embeddings.json")  # vector cache, keyed by snippet id

client = Mistral(api_key=MISTRAL_API_KEY)

# ── Embedding helpers ─────────────────────────────────────────────────────────


def embed(texts: list[str]) -> list[list[float]]:
    """Call Mistral and return one vector per text."""
    response = client.embeddings.create(
        model="mistral-embed",
        inputs=texts,
    )
    return [item.embedding for item in response.data]


def snippet_text(snippet: dict) -> str:
    """Combine fields into one searchable string."""
    tags = " ".join(snippet.get("tags", []))
    return f"{snippet['title']} {snippet['description']} {tags} {snippet['address']}"


# ── TOML storage ──────────────────────────────────────────────────────────────


def load_snippets() -> list[dict]:
    if not SNIPPETS_FILE.exists():
        return []
    with open(SNIPPETS_FILE, "rb") as f:
        data = tomllib.load(f)
    return data.get("snippets", [])


def save_snippets(snippets: list[dict]):
    import tomli_w

    with open(SNIPPETS_FILE, "wb") as f:
        tomli_w.dump({"snippets": snippets}, f)


# ── Embedding cache ───────────────────────────────────────────────────────────


def load_embeddings() -> dict:
    if not EMBEDDINGS_FILE.exists():
        return {}
    with open(EMBEDDINGS_FILE) as f:
        return json.load(f)


def save_embeddings(embeddings: dict):
    with open(EMBEDDINGS_FILE, "w") as f:
        json.dump(embeddings, f)


# ── Cosine similarity ─────────────────────────────────────────────────────────


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Commands ──────────────────────────────────────────────────────────────────


def cmd_add(address: str, title: str, description: str, tags: list[str] = []):
    snippets = load_snippets()
    embeddings = load_embeddings()

    # Generate a simple incremental id
    next_id = str(max((int(s["id"]) for s in snippets), default=0) + 1)

    new_snippet = {
        "id": next_id,
        "title": title,
        "address": address,
        "description": description,
        "tags": tags,
    }

    # Embed and cache
    vector = embed([snippet_text(new_snippet)])[0]
    embeddings[next_id] = vector

    snippets.append(new_snippet)
    save_snippets(snippets)
    save_embeddings(embeddings)

    print(f"✓ Added snippet #{next_id}: {title}")


def cmd_search(query: str, top_k: int = 5):
    snippets = load_snippets()
    embeddings = load_embeddings()

    if not snippets:
        print("No snippets yet. Add some with: python snippetti.py add ...")
        return

    query_vec = embed([query])[0]

    scored = []
    for snippet in snippets:
        sid = snippet["id"]
        if sid not in embeddings:
            continue
        sim = cosine_similarity(query_vec, embeddings[sid])
        scored.append((sim, snippet))

    scored.sort(key=lambda x: x[0], reverse=True)

    print(f'\n🔍 Results for: "{query}"\n')
    for sim, s in scored[:top_k]:
        print(f"  [{sim:.2f}] {s['title']}")
        print(f"         {s['address']}")
        print(f"         {s['description']}")
        if s.get("tags"):
            print(f"         tags: {', '.join(s['tags'])}")
        print()


def cmd_list():
    snippets = load_snippets()
    if not snippets:
        print("No snippets yet.")
        return
    print(f"\n📁 {len(snippets)} snippet(s):\n")
    for s in snippets:
        print(f"  #{s['id']} {s['title']}")
        print(f"     {s['address']}")
        print(f"     {s['description']}")
        print()


# ── Entry point ───────────────────────────────────────────────────────────────


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    command = args[0]

    if command == "add":
        if len(args) < 4:
            print(
                "Usage: python snippetti.py add <address> <title> <description> [tag1 tag2 ...]"
            )
            return
        address = args[1]
        title = args[2]
        description = args[3]
        tags = args[4:]
        cmd_add(address, title, description, tags)

    elif command == "search":
        if len(args) < 2:
            print("Usage: python snippetti.py search <query>")
            return
        cmd_search(" ".join(args[1:]))

    elif command == "list":
        cmd_list()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
