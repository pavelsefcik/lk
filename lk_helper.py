#!/usr/bin/env python3
"""
lk helper - called by the lk zsh function.
Usage:
  lk_helper.py add <path>        -> prompt for title/description, save entry
  lk_helper.py search <query>    -> search entries, write chosen path to ~/.lk_result
"""

import sys
import json
from pathlib import Path

DATA_FILE = Path.home() / ".lk_data.json"


def load():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save(entries):
    with open(DATA_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def cmd_add(path):
    p = Path(path).expanduser().resolve()
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

    entries.append({
        "path": str(p),
        "title": title,
        "description": description
    })
    save(entries)
    print(f"Saved: {title}", file=sys.stderr)


def cmd_search(query):
    entries = load()
    if not entries:
        print("No entries yet. Add one with: lk /some/path", file=sys.stderr)
        sys.exit(1)

    q = query.lower()
    matches = []
    for e in entries:
        haystack = f"{e['title']} {e['description']} {e['path']}".lower()
        if q in haystack:
            matches.append(e)

    if not matches:
        print(f"No results for: {query}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Results for: {query}\n", file=sys.stderr)
    for i, e in enumerate(matches, 1):
        print(f"  {i})  {e['title']}", file=sys.stderr)
        if e["description"]:
            print(f"      {e['description']}", file=sys.stderr)
        print(f"      {e['path']}", file=sys.stderr)
        print("", file=sys.stderr)

    try:
        choice = input("  Pick: ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            tmp = Path.home() / ".lk_result"
            tmp.write_text(matches[idx]["path"])
        else:
            print("Invalid choice.", file=sys.stderr)
            sys.exit(1)
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    command = args[0]
    argument = " ".join(args[1:])

    if command == "add":
        cmd_add(argument)
    elif command == "search":
        cmd_search(argument)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
