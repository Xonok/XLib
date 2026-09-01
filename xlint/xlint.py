import argparse
import re
import sys
from pathlib import Path

_DEF_PREFIX_RE = re.compile(r"^\s*(async\s+def|def)\s+\w+")
_SPACE_INDENT_RE = re.compile(r"^ +\S")

def is_ignored(path):
	parts = set(path.parts)
	return "__pycache__" in parts or ".git" in parts

def python_files(paths):
	found = []
	for entry in paths:
		if entry.is_file() and entry.suffix == ".py":
			found.append(entry)
		elif entry.is_dir():
			for path in sorted(entry.rglob("*.py")):
				if not is_ignored(path):
					found.append(path)
	return found

def check_double_blank(lines):
	report = []
	for index, (prev, current) in enumerate(zip(lines, lines[1:]), start=2):
		if prev == "" and current == "":
			report.append((index, "double blank line"))
	return report

def check_space_indent(lines):
	report = []
	for index, line in enumerate(lines, start=1):
		if _SPACE_INDENT_RE.match(line):
			report.append((index, "indented with spaces"))
	return report

def check_trailing_whitespace(lines):
	report = []
	for index, line in enumerate(lines, start=1):
		if line != line.rstrip():
			report.append((index, "trailing whitespace"))
	return report

def check_def_one_line(lines):
	report = []
	for index, line in enumerate(lines, start=1):
		open_paren = line.find("(")
		if open_paren == -1:
			continue
		if not _DEF_PREFIX_RE.match(line[:open_paren]):
			continue
		if not re.match(r"\(.*\)\s*:\s*$", line[open_paren:]):
			report.append((index, "function definition split across lines"))
	return report

def check_final_newline(lines):
	if lines and not lines[-1].endswith("\n"):
		return [(len(lines), "missing final newline")]
	return []

def main():
	parser = argparse.ArgumentParser(description="Check python files against XLib style rules")
	parser.add_argument("paths", nargs="+", type=Path)
	parser.add_argument("--no-double-blank", action="store_true", help="disable double blank line check")
	parser.add_argument("--no-space-indent", action="store_true", help="disable space indentation check")
	parser.add_argument("--no-trailing", action="store_true", help="disable trailing whitespace check")
	parser.add_argument("--no-def-one-line", action="store_true", help="disable one-line function definition check")
	parser.add_argument("--no-final-newline", action="store_true", help="disable final newline check")
	args = parser.parse_args()

	problems = []
	for path in python_files(args.paths):
		lines = path.read_text().splitlines(keepends=True)
		text_lines = [line.rstrip("\n") for line in lines]
		if not args.no_double_blank:
			problems.extend((path, line, msg) for line, msg in check_double_blank(text_lines))
		if not args.no_space_indent:
			problems.extend((path, line, msg) for line, msg in check_space_indent(text_lines))
		if not args.no_trailing:
			problems.extend((path, line, msg) for line, msg in check_trailing_whitespace(text_lines))
		if not args.no_def_one_line:
			problems.extend((path, line, msg) for line, msg in check_def_one_line(text_lines))
		if not args.no_final_newline:
			problems.extend((path, line, msg) for line, msg in check_final_newline(lines))

	if not problems:
		return 0
	for path, line, msg in problems:
		print(f"{path}:{line}: {msg}")
	return 1

if __name__ == "__main__":
	sys.exit(main())
