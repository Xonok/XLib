import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path
try:
	from ._io import *
except ImportError:
	from _io import *
def check_js_trailing_whitespace(lines):
	"""Trailing whitespace check for JS/TS — same as Python, no Markdown exception."""
	report = []
	for index, line in enumerate(lines, start=1):
		if line != line.rstrip() and line.strip():
			report.append((index, "trailing whitespace"))
	return report
def check_js_double_blank(lines):
	"""Double blank line check for JS/TS — same as Python/Markdown."""
	report = []
	for index, (prev, current) in enumerate(zip(lines, lines[1:]), start=2):
		if prev == "" and current == "":
			report.append((index, "double blank line"))
	return report
def check_js_space_indent(lines, exempt):
	"""Space indentation check for JS/TS — tabs only, with exempt spans."""
	report = []
	for index, line in enumerate(lines, start=1):
		if index in exempt:
			continue
		if _SPACE_INDENT_RE.match(line):
			report.append((index, "indented with spaces"))
	return report
def check_js_final_newline(lines):
	"""Final newline check for JS/TS — file must end with exactly one newline."""
	if lines and not lines[-1].endswith("\n"):
		return [(len(lines), "missing final newline")]
	return []
def check_js_trailing_blank(lines):
	"""Trailing blank line check for JS/TS — no empty line at end after real content."""
	if len(lines) < 2 or lines[-1].strip():
		return []
	if lines[-2].strip():
		return [(len(lines), "trailing blank line at end of file")]
	return []
def _js_exempt_spans(lines):
	"""Map each line number to a list of (start_col, end_col) spans exempt from checks.

	Covers string literals (single/double quoted), template literals (backtick),
	line comments (//), block comments (/* */), and regex literals (/pattern/flags).

	Uses a simple state machine — no parser — because the exemption rules only need
	to know where literal content lives, not the full AST.
	"""
	exempt = {}
	source = "\n".join(lines) + "\n"
	i = 0
	line = 1
	col = 0
	line_start = 0

	while i < len(source):
		ch = source[i]

		if ch == "\n":
			line += 1
			col = 0
			line_start = i + 1
			i += 1
			continue

		# Single-line comment //
		if ch == "/" and i + 1 < len(source) and source[i + 1] == "/":
			start_line = line
			start_col = col
			# Consume to end of line
			while i < len(source) and source[i] != "\n":
				i += 1
				col += 1
			end_col = col
			if start_line not in exempt:
				exempt[start_line] = []
			exempt[start_line].append((start_col, end_col))
			continue

		# Block comment /* ... */
		if ch == "/" and i + 1 < len(source) and source[i + 1] == "*":
			start_line = line
			start_col = col
			i += 2
			col += 2
			while i + 1 < len(source):
				if source[i] == "\n":
					line += 1
					col = 0
					line_start = i + 1
					i += 1
				elif source[i] == "*" and source[i + 1] == "/":
					i += 2
					col += 2
					break
				else:
					i += 1
					col += 1
			end_line = line
			end_col = col
			for ln in range(start_line, end_line + 1):
				if ln not in exempt:
					exempt[ln] = []
				if ln == start_line and ln == end_line:
					exempt[ln].append((start_col, end_col))
				elif ln == start_line:
					exempt[ln].append((start_col, len(lines[ln - 1])))
				elif ln == end_line:
					exempt[ln].append((0, end_col))
				else:
					exempt[ln].append((0, len(lines[ln - 1])))
			continue

		# String literals: '...' or "..." (with escape handling)
		if ch == "'" or ch == '"':
			quote = ch
			start_line = line
			start_col = col
			i += 1
			col += 1
			while i < len(source):
				if source[i] == "\n":
					# Unclosed string - treat as ending at line end
					break
				if source[i] == "\\":
					i += 2
					col += 2
					continue
				if source[i] == quote:
					i += 1
					col += 1
					break
				i += 1
				col += 1
			end_line = line
			end_col = col
			for ln in range(start_line, end_line + 1):
				if ln not in exempt:
					exempt[ln] = []
				if ln == start_line and ln == end_line:
					exempt[ln].append((start_col, end_col))
				elif ln == start_line:
					exempt[ln].append((start_col, len(lines[ln - 1])))
				elif ln == end_line:
					exempt[ln].append((0, end_col))
				else:
					exempt[ln].append((0, len(lines[ln - 1])))
			continue

		# Template literals: `...` (with ${...} interpolation and escape handling)
		if ch == "`":
			start_line = line
			start_col = col
			i += 1
			col += 1
			while i < len(source):
				if source[i] == "\n":
					line += 1
					col = 0
					line_start = i + 1
					i += 1
					continue
				if source[i] == "\\":
					i += 2
					col += 2
					continue
				if source[i] == "$" and i + 1 < len(source) and source[i + 1] == "{":
					# Skip interpolation - treat as part of template
					i += 2
					col += 2
					continue
				if source[i] == "`":
					i += 1
					col += 1
					break
				i += 1
				col += 1
			end_line = line
			end_col = col
			for ln in range(start_line, end_line + 1):
				if ln not in exempt:
					exempt[ln] = []
				if ln == start_line and ln == end_line:
					exempt[ln].append((start_col, end_col))
				elif ln == start_line:
					exempt[ln].append((start_col, len(lines[ln - 1])))
				elif ln == end_line:
					exempt[ln].append((0, end_col))
				else:
					exempt[ln].append((0, len(lines[ln - 1])))
			continue

		# Regex literals: /pattern/flags (heuristic: / not preceded by identifier, (, [, {, ,, ;, :, =, !, &, |, ?, +, -, *, %, ~, ^)
		# This is a best-effort approximation without a full parser
		if ch == "/":
			# Look back to see if this could be a regex
			prev_i = i - 1
			while prev_i >= 0 and source[prev_i] in " \t\r\n":
				prev_i -= 1
			prev_char = source[prev_i] if prev_i >= 0 else ""
			# Regex appears after: ( [ { , ; : = ! & | ? + - * % ~ ^ > < return throw case
			# Not after: identifier, ), ], }, string, number, regex, `, null, true, false, this
			is_regex = prev_char in "([{,;:=!&|?+-*%~^<>"

			if is_regex:
				start_line = line
				start_col = col
				i += 1
				col += 1
				in_class = False
				while i < len(source):
					if source[i] == "\n":
						# Unclosed regex
						break
					if source[i] == "\\":
						i += 2
						col += 2
						continue
					if source[i] == "[" and not in_class:
						in_class = True
					elif source[i] == "]" and in_class:
						in_class = False
					elif source[i] == "/" and not in_class:
						i += 1
						col += 1
						# Consume flags
						while i < len(source) and source[i].isalpha():
							i += 1
							col += 1
						break
					i += 1
					col += 1
				end_line = line
				end_col = col
				for ln in range(start_line, end_line + 1):
					if ln not in exempt:
						exempt[ln] = []
					if ln == start_line and ln == end_line:
						exempt[ln].append((start_col, end_col))
					elif ln == start_line:
						exempt[ln].append((start_col, len(lines[ln - 1])))
					elif ln == end_line:
						exempt[ln].append((0, end_col))
					else:
						exempt[ln].append((0, len(lines[ln - 1])))
				continue

		i += 1
		col += 1

	return exempt
def _js_exempt_lines(lines):
	"""Return set of line numbers that are inside JS/TS literals or comments.

	These lines may start with spaces as part of the literal/comment content and should be
	exempt from the space-indentation check. Mirrors `_python_string_lines`.
	"""
	spans = _js_exempt_spans(lines)
	# A line is exempt if it has any exempt span (string, template, comment, regex)
	return set(spans.keys())

__all__ = ['check_js_trailing_whitespace', 'check_js_double_blank', 'check_js_space_indent', 'check_js_final_newline', 'check_js_trailing_blank', '_js_exempt_spans', '_js_exempt_lines']
