#!/usr/bin/env python3
"""
lk helper - called by the lk zsh function.
Usage:
  lk <path>     -> prompt for title/description, save entry
  lk <query>    -> search entries, open chosen path in Finder
"""

import sys
import json
import os
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse, unquote

BOLD      = "\033[1m"
DIM       = "\033[2m"
UNDERLINE = "\033[4m"
RESET     = "\033[0m"

LK_DIR = Path.home() / ".lk"
DATA_FILE = LK_DIR / "lk_data.json"
RESULT_FILE = LK_DIR / "lk_result"


def load():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save(entries):
    with open(DATA_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def normalize_path(path_str):
    """Converts smb:// or encoded paths to standard /Volumes/ paths."""
    if path_str.startswith("smb://"):
        parsed = urlparse(path_str)
        return "/Volumes" + unquote(parsed.path)
    return os.path.expanduser(path_str)


def cmd_add(path_str):
    normalized = normalize_path(path_str)
    p = Path(normalized).resolve()

    entries = load()
    for e in entries:
        if e["path"] == str(p):
            print(f"Already saved: {e['title']} -> {p}", file=sys.stderr)
            sys.exit(1)

    print(f"\nSaving: {p}", file=sys.stderr)
    title = input("Title: ").strip()
    if not title:
        print("Cancelled.", file=sys.stderr)
        sys.exit(1)
    description = input("Description (optional): ").strip()

    entries.append({"path": str(p), "title": title, "description": description})
    save(entries)
    print(f"Saved: {title}", file=sys.stderr)


def cmd_search(query):
    entries = load()
    if not entries:
        print("No entries yet. Add one with: lk /some/path", file=sys.stderr)
        sys.exit(1)

    def word_matches(word, haystack):
        if word in haystack:
            return True
        return any(SequenceMatcher(None, word, hw).ratio() >= 0.8 for hw in haystack.split())

    words = query.lower().split()
    matches = [e for e in entries if all(word_matches(w, f"{e['title']} {e['description']} {e['path']}".lower()) for w in words)]

    if not matches:
        print(f"No results for: {query}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  {UNDERLINE}Results for {BOLD}{query}{RESET}\n", file=sys.stderr)
    for i, e in enumerate(matches, 1):
        print(f"  {i}  {BOLD}{e['title']}{RESET}", file=sys.stderr)
        if e["description"]:
            print(f"     {DIM}{e['description']}{RESET}", file=sys.stderr)
        print(f"     {DIM}{e['path']}{RESET}", file=sys.stderr)
        print("", file=sys.stderr)

    try:
        choice = input("  Pick: ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            RESULT_FILE.write_text(matches[idx]["path"])
            print("", file=sys.stderr)
        else:
            print("Invalid choice.", file=sys.stderr)
            sys.exit(1)
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Remove result file from previous runs
    if RESULT_FILE.exists():
        RESULT_FILE.unlink()

    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    input_str = " ".join(args)

    if input_str.startswith(("smb://", "/", "./", "../", "~")):
        cmd_add(input_str)
    else:
        cmd_search(input_str)
