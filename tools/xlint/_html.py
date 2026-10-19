"""Html checks for xlint: tag structure and indentation.

The three html rules the human ruled on 2026-10-19 (epi `YFJZRYC`), on top of
the generic ones every language gets:

- every non-void tag is closed explicitly — no optional end tags, no implicit
  closing;
- a closing tag that should not be there is a finding in all three of its
  readings: a closer for a void element, a closer with no matching open, and a
  closer that does not match the innermost open;
- indentation is checked twice over: the depth of a line must be the depth the
  nesting gives it, and the indent must be tabs rather than spaces.

The nesting places a line that starts with a tag opening an element, or with a
tag closing one: the line sits at the level of that element. It does not place
a line of text, a comment, or a lone leaf element — the prose in an element is
written at the element's own level or one deeper, and the nesting does not say
which, so the rule leaves it alone rather than pick one and call the other a
mistake.

The depth is measured in the file's own unit — a tab, or the greatest common
divisor of the file's space runs — because counting tabs in a space-indented
file reports a depth where the real finding is the unit.

The tokenizer skips what is not markup. A comment's content is markup the author
commented out, and it opens and closes nothing; a doctype is not a tag; and the
content of a raw-text element is text rather than tags, so a `<` in a script
does not open one.
"""

import re
from bisect import bisect_right
from math import gcd

VOID_ELEMENTS = frozenset({
	"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
	"param", "source", "track", "wbr",
})
RAW_TEXT_ELEMENTS = frozenset({"script", "style", "textarea", "title"})
_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9:_.-]*")

def check_html(lines: list[str]) -> dict[str, list[tuple[int, str]]]:
	"""Every html finding in `lines`, keyed by the rule that found it.

	The keys are "unclosed", "bad_closer" and "depth" — the three html rules, so
	that the caller can switch each of them off on its own.
	"""
	text = "\n".join(lines)
	tags = _scan(text, _line_starts(text))
	problems, depths = _walk(lines, tags)
	problems["depth"] = _depth_problems(lines, depths)
	return problems

def _line_starts(text: str) -> list[int]:
	"""The offset each line starts at, so that a position reads as a line."""
	starts = [0]
	for index, char in enumerate(text):
		if char == "\n":
			starts.append(index + 1)
	return starts

def _scan(text: str, starts: list[int]) -> list[tuple[str, str, int]]:
	"""Every tag in `text`, in document order, as (kind, name, line).

	`kind` is "open", "close" or "self_closing". A void element's opening tag is
	"open" — the walk knows the void elements and does not push them.
	"""
	tags = []
	index = 0
	length = len(text)
	while index < length:
		open_at = text.find("<", index)
		if open_at == -1:
			break
		if text.startswith("<!--", open_at):
			end = text.find("-->", open_at + 4)
			index = length if end == -1 else end + 3
			continue
		if text.startswith("<!", open_at) or text.startswith("<?", open_at):
			end = text.find(">", open_at)
			index = length if end == -1 else end + 1
			continue
		if text.startswith("</", open_at):
			name = _read_name(text, open_at + 2)
			if name is None:
				index = open_at + 1
				continue
			end = text.find(">", open_at)
			index = length if end == -1 else end + 1
			tags.append(("close", name, _line_of(starts, open_at)))
			continue
		name = _read_name(text, open_at + 1)
		if name is None:
			index = open_at + 1
			continue
		end, self_closing = _tag_end(text, open_at + 1 + len(name))
		index = end
		tags.append(("self_closing" if self_closing else "open", name, _line_of(starts, open_at)))
		if not self_closing and name in RAW_TEXT_ELEMENTS:
			index = _raw_text_end(text, index, name)
	return tags

def _line_of(starts: list[int], index: int) -> int:
	"""The 1-based line the offset `index` sits on."""
	return bisect_right(starts, index)

def _read_name(text: str, index: int) -> str | None:
	"""The element name at `index`, lowercased, or None when no name is there."""
	match = _NAME_RE.match(text, index)
	if match is None:
		return None
	return match.group().lower()

def _tag_end(text: str, index: int) -> tuple[int, bool]:
	"""Where the tag ends, and whether it closes itself.

	The scan stops at the first `>` outside a quoted attribute value, so a `>` in
	an attribute does not end the tag early.
	"""
	quote = None
	length = len(text)
	while index < length:
		char = text[index]
		if quote is not None:
			if char == quote:
				quote = None
		elif char in "\"'":
			quote = char
		elif char == ">":
			back = index - 1
			while back >= 0 and text[back] in " \t\n\r":
				back -= 1
			return index + 1, back >= 0 and text[back] == "/"
		index += 1
	return length, False

def _raw_text_end(text: str, index: int, name: str) -> int:
	"""Where the raw text of `name` ends: the `<` of its closing tag, or the end of the text."""
	lowered = text.lower()
	closing = "</" + name
	at = index
	while True:
		at = lowered.find(closing, at)
		if at == -1:
			return len(text)
		after = text[at + len(closing):at + len(closing) + 1]
		if after == "" or after in " \t\n\r>/":
			return at
		at += 1

def _walk(lines: list[str], tags: list[tuple[str, str, int]]) -> tuple[dict[str, list[tuple[int, str]]], dict[int, int]]:
	"""One pass over the tags: pair the closers with the opens, and read each line's depth.

	Returns the structural findings and, per line, the depth the nesting gives
	that line. A line the nesting places is one that starts with a tag opening
	an element, or with a tag closing one: it sits at the level of that element,
	whether the tag opens it or closes it.
	"""
	problems = {"unclosed": [], "bad_closer": []}
	depths = {}
	by_line = {}
	for kind, name, line in tags:
		by_line.setdefault(line, []).append((kind, name))
	open_tags = []
	for line in range(1, len(lines) + 1):
		line_tags = by_line.get(line, ())
		placed = _places_line(lines[line - 1], line_tags)
		for position, (kind, name) in enumerate(line_tags):
			if kind == "open":
				if position == 0 and placed:
					depths[line] = len(open_tags)
				if name not in VOID_ELEMENTS:
					open_tags.append((name, line))
				continue
			if kind == "self_closing":
				continue
			level, finding = _close(open_tags, name)
			if finding is not None:
				problems["bad_closer"].append((line, finding))
			if position == 0 and placed and level is not None:
				depths[line] = level
	for name, line in open_tags:
		problems["unclosed"].append((line, f"unclosed tag <{name}>"))
	return problems, depths

def _places_line(line: str, line_tags: list[tuple[str, str]]) -> bool:
	"""True when the nesting places this line: it starts with a tag that opens or closes an element.

	A line of text, a comment, and a lone leaf element are not placed by the
	nesting. The prose in an element is written at the element's own level or one
	deeper, and the nesting does not say which; a leaf element opens no level of
	its own, so there is nothing for it to sit at.
	"""
	body = line.lstrip()
	if not body.startswith("<") or body.startswith("<!--") or not line_tags:
		return False
	kind, name = line_tags[0]
	if kind == "close":
		return True
	return kind == "open" and name not in VOID_ELEMENTS

def _close(open_tags: list[tuple[str, int]], name: str) -> tuple[int | None, str | None]:
	"""Apply a closing tag to the open stack.

	Returns the level of the element the tag closes and the finding it produced,
	if any. A closer for a void element, a closer with no matching open, and a
	closer that does not match the innermost open are the three findings. A
	closer that matches an open element below the innermost closes it and
	everything above it, so the elements it closed on the way are not reported
	as unclosed as well.
	"""
	if name in VOID_ELEMENTS:
		return None, f"closing tag </{name}> for a void element"
	match = _match_index(open_tags, name)
	if match is None:
		return None, f"closing tag </{name}> with no matching open tag"
	finding = None
	if match != len(open_tags) - 1:
		finding = f"closing tag </{name}> does not match the open <{open_tags[-1][0]}>"
	del open_tags[match:]
	return match, finding

def _match_index(open_tags: list[tuple[str, int]], name: str) -> int | None:
	"""Where in the open stack the element named `name` sits, or None if it is not open."""
	for index in range(len(open_tags) - 1, -1, -1):
		if open_tags[index][0] == name:
			return index
	return None

def _depth_problems(lines: list[str], depths: dict[int, int]) -> list[tuple[int, str]]:
	"""The lines whose indent is not the depth the nesting gives them."""
	unit = _indent_unit(lines)
	problems = []
	for line in range(1, len(lines) + 1):
		text = lines[line - 1]
		if not text.strip():
			continue
		want = depths.get(line)
		if want is None:
			continue
		level = _indent_level(text, unit)
		if level is None:
			continue
		if want == level:
			continue
		problems.append((line, f"indentation depth mismatch: expected {want}, got {level}"))
	return problems

def _indent_unit(lines: list[str]) -> str:
	"""One level of indentation, written the way this file writes it.

	A tab when any line is indented with one, and otherwise the greatest common
	divisor of the file's space runs, as spaces. The unit is the file's own:
	counting tabs in a space-indented file reports a depth where the real finding
	is the unit.
	"""
	runs = []
	for line in lines:
		indent = line[:len(line) - len(line.lstrip())]
		if not indent:
			continue
		if "\t" in indent:
			return "\t"
		runs.append(len(indent))
	if not runs:
		return "\t"
	width = runs[0]
	for run in runs[1:]:
		width = gcd(width, run)
	return " " * width

def _indent_level(line: str, unit: str) -> int | None:
	"""The depth of the line's indent in the file's unit, or None when the indent is not written in it."""
	indent = line[:len(line) - len(line.lstrip())]
	if not indent:
		return 0
	levels, remainder = divmod(len(indent), len(unit))
	if remainder or indent != unit * levels:
		return None
	return levels
