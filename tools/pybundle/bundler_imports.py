"""What each import binds, where it lives, and whether that is here — D6, D8 and
D16.

One entry per import statement, in source order, because D8's removal rule is
stated per statement: `import helper, os` is one statement with two targets, and
without the link from entry to statement a specific line cannot be deleted.

`prefix` on a target is left for `inline` to fill. D3 makes the root's prefix the
empty one and says the exception is per file identity, which `imports` cannot
know — it is handed the root *folder*, never the entry (D15).
"""

import re
from pathlib import Path

class IMPORT_FILE_NOT_FOUND(Exception):
	"""A file an import named is not there, and a relative import cannot be a
	global — so there is nothing to leave in place either."""

_CLAUSE = re.compile(r":\s*((?:import|from)\s)")
_HEAD = re.compile(r"^(import|from)\s+(.*)$", re.DOTALL)

def imports(statements: list, modpath: str, root: str) -> list:
	"""One entry per import statement, in the order the statements are in.

	Each entry carries the statement it came from, what kind of import it is, its
	targets — each a modpath or None when the target is not here, and the name it
	binds — and whether it was written relative.
	"""
	found = []
	for statement in statements:
		clause = _clause(statement["text"])
		if clause is not None:
			found.append(_entry(clause, statement, modpath, root))
	return found

def _clause(text: str):
	"""The import inside a statement, or None when it holds none.

	An import under a one-line compound counts — the Edge cases section says all
	imports are handled as if at the top of the file, and `if False: import x`
	inlines x.
	"""
	stripped = text.strip()
	if _HEAD.match(stripped):
		return stripped
	if (head := _CLAUSE.search(text)):
		return text[head.start(1):].strip()
	return None

def _entry(clause: str, statement: dict, modpath: str, root: str) -> dict:
	"""The one entry an import statement gets."""
	kind, rest = _HEAD.match(clause).groups()
	if kind == "import":
		return _entry_of(statement, "module", False, None, [_module(part, modpath, root) for part in rest.split(",")])
	source, _, names = rest.partition(" import ")
	relative = source.startswith(".")
	base, module = _resolves(source, modpath)
	if names.strip() == "*":
		return _entry_of(statement, "star", relative, source, [_star(base, module, modpath, root, relative)])
	parts = [_from(base, module, part, modpath, root, relative) for part in _names(names)]
	shaped = "module" if parts and all(part["kind"] == "module" for part in parts) else "name"
	return _entry_of(statement, shaped, relative, source, parts)

def _entry_of(statement: dict, kind: str, relative: bool, source, targets: list) -> dict:
	return {"statement": statement, "kind": kind, "relative": relative, "source": source,
		"targets": targets, "defined": []}

def _names(text: str) -> list:
	"""A name import's names, which may be written in parentheses."""
	return [part.strip() for part in text.strip().strip("()").split(",") if part.strip()]

def _module(part: str, modpath: str, root: str) -> dict:
	"""One target of an `import a, b as c` statement.

	`import a.b` binds `a`, a name the statement does not spell, which is the one
	case D20 keeps verbatim rather than aliasing — so `dotted` is recorded here
	and the rebind is written later beside the statement that binds it.
	"""
	written, _, alias = part.strip().partition(" as ")
	written = written.strip()
	alias = alias.strip() or None
	return _target(written, written.split(".")[0], alias, modpath, root, "." in written, False)

def _star(base: str, module: str, modpath: str, root: str, relative: bool) -> dict:
	"""The single target of a `from x import *`."""
	joined = _joined(base, module)
	found = _here(joined, root, relative, joined)
	return {"modpath": joined if found is not None else None, "name": module, "alias": None,
		"binds": module, "dotted": False, "local": found is not None, "prefix": None}

def _from(base: str, module: str, part: str, modpath: str, root: str, relative: bool) -> dict:
	"""One target of a `from x import a, b as c` statement.

	**A name that turns out to be a module is a module import, not a name
	import.** `from . import api` and `from helper import count` are written
	alike and mean different things, and which is which is a question about the
	disk. R3's worked example is the first shape: `api` names a file, so a use of
	it reaches that file's prefixed globals rather than rebinding one of them.

	**Locality is judged on the module, not on the name**, so `helper` being here
	is what makes `from helper import count` local even though nothing here is
	called `helper.count`. An empty module — `from . import api` — names nothing,
	and the name is the only thing to judge on.
	"""
	name, _, alias = part.partition(" as ")
	name = name.strip()
	alias = alias.strip() or None
	if _found(_joined(base, _joined(module, name)), root) is not None:
		return _target(_joined(base, _joined(module, name)), name, alias, modpath, root, False, relative)
	target = _target(_joined(base, module) if module else name, name, alias, modpath, root, False, relative)
	target["kind"] = "name"
	return target

def _target(candidate: str, name: str, alias, modpath: str, root: str, dotted: bool, relative: bool) -> dict:
	"""One target, decided local or not by whether the file is under the root.

	A missing absolute import is left in place — it may be a global, and D7 puts
	detecting that out of scope. A missing relative one cannot be, so it raises.
	"""
	found = _here(candidate, root, relative, candidate)
	if found is not None and found.name == "__init__.py":
		# D6: importing a folder imports its `__init__.py`, and that contributes
		# `__init__` as an ordinary path component rather than being a special case.
		candidate = f"{candidate}.__init__"
	return {"modpath": candidate if found is not None else None, "name": name, "alias": alias,
		"binds": alias or name, "written": candidate, "dotted": dotted,
		"local": found is not None, "prefix": None, "kind": "module"}

def _here(candidate: str, root: str, relative: bool, what: str):
	"""The file a modpath names, raising when a relative import found nothing."""
	found = _found(candidate, root)
	if found is None and relative:
		raise IMPORT_FILE_NOT_FOUND(f"IMPORT_FILE_NOT_FOUND: {what}")
	return found

def _found(candidate: str, root: str):
	"""The file a modpath names, as a package or as a module (D6 — no special case
	for `__init__.py`, which is an ordinary path component)."""
	if not candidate:
		return None
	base = Path(root) / candidate.replace(".", "/")
	for path in (base.with_suffix(".py"), base / "__init__.py"):
		if path.is_file():
			return path
	return None

def _resolves(source: str, modpath: str) -> tuple:
	"""The folder a `from ... x import y` starts from, and the module it names.

	Leading dots count up out of the importing file's package, which is ordinary
	python behaviour and is what makes R3's `from . import api` in
	`py/command/map.py` behave as `py.command.api`.

	**A modpath may be written with slashes as well as dots.** R3 spells one
	dotted and D12 joins it to a folder, which is the disagreement F21 records and
	leaves open; `test_a_relative_import_yields_one_entry` passes `sub/client`
	while the loop hands this function `sub.client`. Both name the same file, so
	the slash is folded to a dot rather than the discrepancy settled.
	"""
	stripped = source.lstrip(".")
	level = len(source) - len(stripped)
	parts = modpath.replace("/", ".").split(".")[:-1]
	base = parts[:len(parts) - level + 1] if level else []
	return ".".join(base), stripped

def _joined(base: str, module: str) -> str:
	"""A base folder and a module name as one modpath."""
	return ".".join(part for part in (base, module) if part)
