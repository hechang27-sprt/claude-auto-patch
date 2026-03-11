#!/usr/bin/env python3
"""Search Claude Code cli.js for patch targets by keyword.

Usage:
    python search_target.py <cli.js path> "<keyword>" [--context 120] [--max 10]

Output:
    For each match, prints the byte offset and surrounding context as repr().
"""

import argparse
import re
import sys


def search(filepath: str, keyword: str, context: int = 120, max_results: int = 10):
    with open(filepath, "rb") as f:
        data = f.read()

    keyword_bytes = keyword.encode("utf-8")
    pattern = re.compile(
        rb".{0," + str(context).encode() + rb"}"
        + re.escape(keyword_bytes)
        + rb".{0," + str(context).encode() + rb"}"
    )

    matches = list(pattern.finditer(data))
    print(f"Found {len(matches)} match(es) for '{keyword}' in {filepath}")
    print(f"File size: {len(data):,} bytes\n")

    for i, m in enumerate(matches[:max_results]):
        start = m.start()
        end = m.end()
        snippet = m.group()

        # Find the keyword position within the snippet
        kw_pos = snippet.find(keyword_bytes)
        abs_offset = start + kw_pos

        print(f"--- Match {i+1}/{min(len(matches), max_results)} "
              f"(offset {abs_offset:#x} / {abs_offset}) ---")
        print(repr(snippet))
        print()

    if len(matches) > max_results:
        print(f"... and {len(matches) - max_results} more matches (use --max to see more)")


def main():
    parser = argparse.ArgumentParser(description="Search cli.js for patch targets")
    parser.add_argument("file", help="Path to cli.js")
    parser.add_argument("keyword", help="Keyword to search for")
    parser.add_argument("--context", type=int, default=120,
                        help="Bytes of context before/after (default: 120)")
    parser.add_argument("--max", type=int, default=10,
                        help="Max results to show (default: 10)")
    args = parser.parse_args()

    search(args.file, args.keyword, args.context, args.max)


if __name__ == "__main__":
    main()
