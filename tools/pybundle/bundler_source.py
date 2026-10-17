"""What a python file consists of — D1, D2, D16 and D22.

One function, and it is a leaf: nothing else here imports anything from the
bundler (R6.3). `tokenize` is the source of truth because D1 makes a statement a
*logical* line, and only the tokenizer knows where one ends.
"""

import io,re,tokenize

_INDENT = re.compile(r"[ \t]*")

# Tokens that say nothing about where a statement starts or ends.
_SKIP = frozenset((tokenize.INDENT,tokenize.DEDENT,tokenize.COMMENT,tokenize.ENCODING,tokenize.ENDMARKER))

def statements(text: str) -> list:
	"""The file's statements in source order, each a `text`/`indent` dictionary.

	`text` is the statement's own source — every line of it, first line's
	indentation included, no trailing newline. `indent` is that same leading
	whitespace as a string, which is what D21 needs and a column count could not
	be. Empty lines and comment-only lines are statements too (D22): the rules
	about what a statement is exist so a multi-line statement is not broken
	apart, not so that anything is removed.
	"""
	found = []
	lines = text.splitlines()
	start = None
	for token in _tokens(text):
		kind, position = token[0], token[2]
		if kind == tokenize.NEWLINE:
			start = _closed(found, lines, start, position[0])
		elif kind == tokenize.NL and start is None:
			found.append(_entry(lines[position[0] - 1]))
		elif start is None and kind not in _SKIP:
			start = position[0] - 1
	_closed(found, lines, start, len(lines))
	return found

def _tokens(text: str):
	"""The tokenizer's stream, stopping where it cannot go further.

	A file whose last line has no newline is not an error to this tool, and
	tokenize raises rather than yielding for it, so the tokens so far are what
	there is. D1's guarantees come from the stream itself.
	"""
	try:
		yield from tokenize.generate_tokens(io.StringIO(text).readline)
	except (tokenize.TokenError, IndentationError):
		return

def _entry(line: str) -> dict:
	"""One statement that occupies a line of its own."""
	return {"text": line, "indent": _INDENT.match(line).group()}

def _closed(found: list, lines: list, start, end: int):
	"""The statement running from line `start` to line `end`, if one is running."""
	if start is None:
		return None
	found.append({"text": "\n".join(lines[start:end]), "indent": _INDENT.match(lines[start]).group()})
	return None
