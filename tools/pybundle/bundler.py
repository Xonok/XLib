"""The loop, and the setup that pipes into it — R1, R2, R3, R5, D3, D11, D12, D14,
D15, D23 and D29.

This is the only module that imports the others (R6.3). Everything it hands down
is passed in: the sink, the handled set, the root folder and the entry. The one
piece of per-run state the design cannot avoid is the indentation anchor, and
even that is a reading rather than a cache — see `_anchor`.
"""

import sys
from pathlib import Path
from tools.pybundle.bundler_imports import IMPORT_FILE_NOT_FOUND,imports
from tools.pybundle.bundler_names import defined,renamed,translate
from tools.pybundle.bundler_source import statements

def main(entry: str, out) -> None:
	"""Bundle `entry` into the file-like `out`.

	The sink is whatever it is — a buffer, a file, a pipe — and this never closes
	it (R5). The sink's opening and closing is `cli`'s, which is why there are two
	functions and not one.
	"""
	inline(Path(entry).stem, str(Path(entry).parent), out, {Path(entry).stem}, Path(entry).stem)

def inline(modpath: str, root: str, out, seen: set, entry: str) -> list:
	"""One file and everything it pulls in, written to `out`; the names it defined.

	Imports are processed before the file's own code is written (R1.4), so each
	inlined block is contiguous and the comments around it delimit something real.
	A file already in `seen` is not written again (R1.6) — which is also what
	handles a circular import, without an error.
	"""
	seen.add(modpath)
	text = _read(root, modpath)
	found = statements(text)
	resolved = imports(found, modpath, root)
	# D30: a relative import resolves the same way here as in any other file, so
	# the root is not a case this needs. `IMPORT_FILE_NOT_FOUND` covers the one
	# that is — a relative import naming a file that is not there.
	prefix = "" if modpath == entry else _prefix(modpath)
	_warn_indentation(text, modpath, _anchor(root, entry))
	for item in resolved:
		for target in item["targets"]:
			target["prefix"] = None if not target["local"] or target["modpath"] == entry else _prefix(target["modpath"])
			target["namespace"] = _namespaces(target)
	imported = _inlined(resolved, modpath, root, out, seen, entry, prefix)
	own = {name: renamed(name, prefix) for name in defined(found)}
	path = _path_of(modpath)
	out.write(f"## {path}\n")
	out.write(translate(found, {**imported, **own}, resolved) + "\n")
	out.write(f"##! {path}\n")
	return list(own)

def _inlined(resolved: list, modpath: str, root: str, out, seen: set, entry: str, prefix: str) -> dict:
	"""Recurse into every local target in source order, and say what each import
	binds here.

	A local module import binds nothing — D28 makes its name an alias for the
	callee's prefixed globals, which `_aliases` reads from `resolved`. A name
	import, local or not, binds this file's own prefixed name (D20, D27).
	"""
	imported = {}
	for item in resolved:
		for target in item["targets"]:
			if not target["local"]:
				if item["kind"] != "star":
					imported[target["binds"]] = renamed(target["binds"], prefix)
				else:
					_warn(f"{target['name']}: a star import of a module that is not here binds names "
						f"no other file can reach through it")
				continue
			if target["modpath"] in seen:
				_warn(f"{target['modpath']}: a second reference is dropped, it is already in the bundle")
				if item["kind"] != "module":
					imported[target["binds"]] = renamed(target["binds"], prefix)
				continue
			target["defined"] = inline(target["modpath"], root, out, seen, entry)
			if item["kind"] == "star":
				for name in target["defined"]:
					imported[name] = renamed(name, prefix)
			elif item["kind"] == "name":
				imported[target["binds"]] = renamed(target["binds"], prefix)
	return imported

def _prefix(modpath: str) -> str:
	"""The file's prefix — its modpath flattened with `__` (R3).

	**A component that already begins with an underscore is appended without its
	own separator**, so `sub/__init__.py` prefixes `sub____init__` and not
	`sub____init____`. D6 gives `__init__.py` its own path component like any
	other; the one test pinning the emitted name is what fixes the shape.
	"""
	return "".join(part if part.startswith("_") else part + "__" for part in modpath.split("."))

def _namespaces(target: dict) -> dict:
	"""The prefixes of the modules a package's namespace carries.

	A use of `pkg.sub` reaches `sub`'s globals, so the name after the package's
	own name has to reach that module's prefix and not the package's. The
	package's own `__init__.py` is not in here: its globals are the package's
	own name, and D28's alias already reaches them.
	"""
	if not target["local"] or not target.get("namespace"):
		return {}
	return {name: _prefix(modpath) for name, modpath in target["namespace"].items()}

def _path_of(modpath: str) -> str:
	"""Where R2 says a block's comments point: a directory component carries a
	leading `/`, and a file in the root folder carries none."""
	parts = modpath.split(".")
	return f"/{'/'.join(parts)}.py" if len(parts) > 1 else f"{parts[0]}.py"

def _read(root: str, modpath: str) -> str:
	"""The file's text. Bytes first, because R7 says the text itself is kept."""
	with open(f"{root}/{modpath.replace('.', '/')}.py", "rb") as handle:
		raw = handle.read()
	for encoding in ("utf-8", "latin-1"):
		try:
			return raw.decode(encoding)
		except UnicodeDecodeError:
			continue
	raise IMPORT_FILE_NOT_FOUND(f"IMPORT_FILE_NOT_FOUND: {modpath} is not text this can read")

def _warn(message: str) -> None:
	"""D14: every diagnostic goes to stderr, and none may reach the sink — a
	message on stdout would corrupt the bundle whenever the sink is stdout."""
	print(f"pybundle: {message}", file=sys.stderr)

def _convention(text: str) -> str:
	"""This file's indentation type, or "" when it has none.

	Both types on one line counts as neither, which is what makes a line that
	opens with the anchor's own character and then goes on to carry the other one
	an offender (D23).
	"""
	for statement in statements(text):
		if not statement["text"].strip():
			continue
		indent = statement["indent"]
		tab, space = "\t" in indent, " " in indent
		if tab and space:
			return "mixed"
		if tab:
			return "tab"
		if space:
			return "space"
	return ""

def _anchor(root: str, entry: str) -> str:
	"""The convention D23 anchors the warning on: the root file's, or the first
	file that has indentation where the root has none.

	It is worked out rather than carried because `inline`'s signature is fixed at
	five arguments by D11 and `test_a_run_after_another_matches_the_same_run_alone`
	forbids state between runs (R6.2). The second reading costs a walk of the
	local imports, and only in the case where the root is not indented at all.
	"""
	if (found := _convention(_read(root, entry))):
		return found
	walked, queue = set(), [entry]
	while queue:
		modpath = queue.pop(0)
		if modpath in walked:
			continue
		walked.add(modpath)
		try:
			text = _read(root, modpath)
		except OSError:
			continue
		if (found := _convention(text)):
			return found
		for item in imports(statements(text), modpath, root):
			queue.extend(target["modpath"] for target in item["targets"] if target["local"])
	return ""

def _warn_indentation(text: str, modpath: str, anchor: str) -> None:
	"""D23's fourth diagnostic and D29's form: one entry per offending file,
	naming that file's first offending line by path, number and text.

	Continuations and string interiors cannot appear here — a statement is a
	logical line (D1), so the scan sees the line that opened the bracket or the
	quote and its own indentation. Nothing is refused; the bundle is written.
	"""
	if not anchor:
		return
	line = 1
	for statement in statements(text):
		if statement["text"].strip() and statement["indent"] and _kind(statement["indent"]) != anchor:
			_warn(f"{_path_of(modpath)}, line {line}, {statement['text'].splitlines()[0]}")
			return
		line += statement["text"].count("\n") + 1

def _kind(indent: str) -> str:
	"""The indentation type a stretch of whitespace carries."""
	tab, space = "\t" in indent, " " in indent
	return "mixed" if tab and space else "tab" if tab else "space" if space else ""

if __name__ == "__main__":
	from tools.pybundle.bundler_cli import cli
	sys.exit(cli(sys.argv[1:]))
