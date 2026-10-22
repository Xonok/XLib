#!/usr/bin/env python3
"""
Check text for the personal identifiers that must not reach a published file.

The rule is `doc/personal-data.md`: this repository is public, so what it
contains — and what the board, which is committed to a branch in it, contains
— names no private project, no colleague, and nothing that only makes sense on
one machine.

**The token list lives outside the repository**, in
`~/.config/xlib/personal-details.txt`, because a check that kept the forbidden
strings in the repository would be the leak it exists to prevent. The loader
is `tools/xlint/_personal.py`; the same list is what the linter checks
tracked files against, so a value that passes this check passes that one too.

Usage:
	python3 tools/check-personal.py --text        # the text to check, on stdin
	python3 tools/check-personal.py FILE...        # files to check
	python3 tools/check-personal.py --pending      # the board's own unsynced writes

Exit status 0 when nothing was found, 1 when something was.
"""

import glob,json,os,sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xlint._personal import find,load_tokens

EPIQ_HOME = os.environ.get("EPIQ_HOME_OVERRIDE") or os.path.expanduser("~/.epiq-global")

def report(source: str, lines: list, tokens: list) -> int:
	"""Print the identifiers found in `lines`; return how many."""
	hits = 0
	for index, token in find(lines, tokens):
		print("%s:%d: personal identifier — %s" % (source, index, token))
		hits += 1
	return hits

def pending_logs() -> list:
	"""The board's pending event logs: the writes that are not published yet.

	A pending file is an actor's own unsynced writes, and the file it is
	drained into is the branch the board is committed to — so this is the one
	place where a personal identifier can still be caught before it is
	published.
	"""
	return sorted(glob.glob(os.path.join(EPIQ_HOME, "worktrees", "*", ".epiq", "events", "*~pending*.jsonl")))

def check_pending(tokens: list) -> int:
	hits = 0
	for path in pending_logs():
		try:
			with open(path, encoding="utf-8") as fh:
				lines = fh.read().splitlines()
		except OSError:
			continue
		found = report(path, lines, tokens)
		if found:
			print("%s: %d personal identifier(s) in an unpublished board write" % (path, found))
			print("  edit the write before it is synced: the board is a public branch")
		hits += found
	return hits

def main() -> None:
	args = sys.argv[1:]
	tokens = load_tokens()
	if not tokens:
		print("no token list at %s — nothing checked" % os.path.expanduser("~/.config/xlib/personal-details.txt"))
		return
	hits = 0
	if not args or args[0] == "--text":
		text = sys.stdin.read()
		hits += report("<stdin>", text.splitlines(), tokens)
	elif args[0] == "--pending":
		hits += check_pending(tokens)
	else:
		for path in args:
			try:
				with open(path, encoding="utf-8") as fh:
					lines = fh.read().splitlines()
			except OSError as exc:
				print("%s: %s" % (path, exc))
				hits += 1
				continue
			hits += report(path, lines, tokens)
	if hits:
		print("%d personal identifier(s) found" % hits)
		raise SystemExit(1)
	print("clean")

if __name__ == "__main__":
	main()
