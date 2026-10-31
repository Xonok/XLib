"""Repo-specific xlint rules for XLib.

A released library under `xlib/` is a frozen, versioned artifact: it must
never name `xlib_dev`, which resolves to the live `dev/` tree. This module
encodes that as a repo rule so the check runs beside the built-ins without
editing `tools/xlint/xlint.py`.
"""

def check_no_xlib_dev(files):
	"""Report any mention of `xlib_dev` in a released file under `xlib/`."""
	report = []
	for path, lines in files:
		for index, line in enumerate(lines, start=1):
			if "xlib_dev" in line:
				report.append((path, index, "a released file must not mention xlib_dev"))
	return report

def rules():
	return [
		{"name": "no-xlib-dev", "paths": ["xlib/**"], "check": check_no_xlib_dev},
	]
