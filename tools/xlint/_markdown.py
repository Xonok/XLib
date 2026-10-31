import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path
try:
	from ._io import *
except ImportError:
	from _io import *
def _frontmatter_exempt(lines):
	if not lines or lines[0] != "---":
		return set()
	for i in range(1, len(lines)):
		if lines[i] == "---":
			return set(range(1, i + 2))
	return set()
def _fence_exempt(lines):
	"""Line numbers inside a fenced code block, including the fence lines themselves.

	A fence is recognised after leading whitespace, so a block nested in a list item is
	a fence rather than a space-indented violation. That is the ordinary way to write
	one, and a rule that makes it unlintable is a rule whose only remedy is to corrupt
	the code to satisfy the linter (`QN1N82Y`).
	"""
	exempt = set()
	in_fence = False
	fence_char = None
	fence_len = 0
	for i, line in enumerate(lines, start=1):
		body = line.lstrip()
		if not body:
			if in_fence:
				exempt.add(i)
			continue
		ch = body[0]
		if ch not in ("`", "~"):
			if in_fence:
				exempt.add(i)
			continue
		count = 0
		for c in body:
			if c == ch:
				count += 1
			else:
				break
		if count >= 3:
			if not in_fence:
				in_fence = True
				fence_char = ch
				fence_len = count
			elif ch == fence_char and count >= fence_len:
				in_fence = False
				fence_char = None
				fence_len = 0
			else:
				exempt.add(i)
		else:
			if in_fence:
				exempt.add(i)
	return exempt
def _markdown_exempt_spans(lines):
	"""Line spans inside fenced code, frontmatter, or inline code spans."""
	exempt = {}
	exempt_set = _frontmatter_exempt(lines)
	exempt_set.update(_fence_exempt(lines))
	# Inline code spans: backtick-delimited on a single line
	for index, line in enumerate(lines, start=1):
		if index in exempt_set:
			continue
		for match in re.finditer(r"`[^`]*`", line):
			start, end = match.span()
			exempt.setdefault(index, []).append((start, end))
	# Convert the set of fully-exempt lines to spans
	for ln in exempt_set:
		if ln <= len(lines):
			exempt[ln] = [(0, len(lines[ln - 1]))]
	return exempt
def _blockquote_exempt(lines):
	"""Line numbers of block-quote lines (lines starting with `> ` after optional whitespace).

	These are exempt from the absolute-path check because quoted material is evidence,
	not a location reference.
	"""
	exempt = set()
	for i, line in enumerate(lines, start=1):
		stripped = line.lstrip()
		if stripped.startswith("> "):
			exempt.add(i)
	return exempt

__all__ = ['_frontmatter_exempt', '_fence_exempt', '_markdown_exempt_spans', '_blockquote_exempt']
