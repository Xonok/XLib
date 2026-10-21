"""What a name is called in the bundle, and what a file looks like with its names
moved — R3, R4, R7, D2, D3, D16, D21 and D22.

`renamed` is the only pure function in the set (D4), so it carries the prefix rule
by itself. `translate` is where a name either becomes its bundled name or is left
alone, which is R4's whole question: a name bound inside a block is that block's
own, and a name reaching past a module is not ours to move.

D21 is why the block scan is below rather than a comparison of `indent`. The two
agree until a project mixes tabs and spaces, and there `'\t' < '    '` is True, so
a block closes on its own first line and a wrong bundle is written with nothing
raised. Matching the tokenizer's own INDENT/DEDENT is the fix D21 names.
"""

import io,keyword,re,tokenize

_SKIP = frozenset((tokenize.INDENT,tokenize.DEDENT,tokenize.COMMENT,tokenize.ENCODING,tokenize.ENDMARKER))
_GLOBAL = re.compile(r"^global\b")
_NONLOCAL = re.compile(r"^nonlocal\b")
_NAMED = re.compile(r"[A-Za-z_]\w*")
_TARGET = re.compile(r"[A-Za-z_]\w*")
_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*(?::[^=]*?)?(?:[-+*/%@&|^]|//|\*\*|<<|>>)?=(?!=)")
_FOR = re.compile(r"^for\s+(.+?)\s+in\b")
_AS = re.compile(r"\bas\s+([A-Za-z_]\w*)")
_WALRUS = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*:=")
_CLAUSE = re.compile(r":\s*(import\b|from\b)\s")
_IMPORT = re.compile(r"^(?:import\s+(?P<module>.+)|from\s+(?P<source>[.\w]+)\s+import\s+(?P<names>.+))$")
_DEF_NAME = re.compile(r"^(?:async\s+)?def\s+([A-Za-z_]\w*)")

def renamed(name: str, prefix: str) -> str:
	"""The name this one is called in the bundle, under `prefix`.

	Leading underscores move in front of the prefix, so a name that was private
	in its own file still reads as private in the bundle. An empty prefix is the
	root exception (D3), and is the identity.

	**A name of exactly two leading underscores keeps one of them behind the
	prefix** — `__foo` becomes `_helper____foo`, where `_foo` and `___foo` move
	all of theirs. The spec states this case as an example beside the others and
	each of the three is pinned by a test, so the exception is written out rather
	than left for the next reader to work out from the shape of the answer.
	"""
	moved = len(name) - len(name.lstrip("_"))
	if moved == 2:
		return "_" + prefix + name
	return "_" * moved + prefix + name[moved:]

def translate(statements: list, renames: dict, resolved: list) -> str:
	"""The file's text with its names moved and its inlined imports gone.

	One string, statements joined with newlines and no trailing newline (D16) —
	`inline` composes the comments around it. `renames` says what each name is
	called here; `resolved` says which import statements were inlined and carries
	each target's prefix and, for a star import, the globals it defines.
	"""
	entries = {id(entry["statement"]): entry for entry in resolved}
	aliases = _aliases(resolved)
	blocks = [[set(), set()]]
	waiting = set()
	out = []
	pending = False
	for depth, index, statement in _scanned(statements):
		while len(blocks) > depth + 1:
			blocks.pop()
		while len(blocks) < depth + 1:
			blocks.append([set(waiting), set()])
			waiting = set()
		entry = entries.get(id(statement))
		if entry is not None:
			kept = _imported(statement, entry, renames)
			if kept is None:
				kept = _emptied(statement, statements, index)
			if kept:
				out.extend(kept)
			else:
				# D32's third rule: a statement the bundler removed must not leave
				# the blank above it next to the blank below it. A blank the source
				# wrote twice is carried and stays that library's own finding.
				pending = bool(out) and out[-1] == "" and _blank_at(statements, index)
			continue
		if pending and not statement["text"].strip():
			pending = False
			continue
		pending = False
		body = statement["text"].strip()
		if _GLOBAL.match(body):
			blocks[-1][1].update(_NAMED.findall(body))
		elif _NONLOCAL.match(body):
			blocks[-1][0].update(_NAMED.findall(body))
		else:
			own, waiting = _bindings(body)
			blocks[-1][0].update(own)
		out.extend(_rewritten(statement["text"], renames, aliases, _shadowed(blocks)))
	if not out:
		return ""
	return "\n".join(out)

def defined(statements: list) -> list:
	"""The names this file defines at module level.

	D12 has `inline` return these, because a star import rebinds exactly them
	(D20). It is the same binding-form list and the same block scan `translate`
	uses — D4's function set describes the core, and this is the one reading of
	that scan the loop needs for itself.
	"""
	found = []
	for depth, _, statement in _scanned(statements):
		body = statement["text"].strip()
		if depth or _IMPORT.match(body):
			continue
		found.extend(_bindings(body)[0])
	return found

def _shadowed(blocks: list) -> set:
	"""The names a use here cannot touch (R4).

	Only blocks below the module count. A module-level name is one this file
	*defines*, which is exactly what gets renamed; a name bound inside a function
	or class is that block's own. A name a block declared `global` is module-level
	however deep it is declared, so it is taken back out.
	"""
	hidden = set().union(*(block[0] for block in blocks[1:])) if len(blocks) > 1 else set()
	return hidden - set().union(*(block[1] for block in blocks))

def _scanned(statements: list):
	"""Each statement with the depth the tokenizer puts it at, in order.

	The same walk `statements` makes, re-run here because D4 says `translate`
	scans blocks internally rather than being handed them. It walks the texts it
	is given, so the nth statement here is the nth statement there.
	"""
	source = "\n".join(statement["text"] for statement in statements)
	depth = 0
	index = 0
	opened = False
	try:
		tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
	except (tokenize.TokenError, IndentationError):
		return
	for token in tokens:
		kind, position = token[0], token[2]
		if kind == tokenize.INDENT:
			depth += 1
			continue
		if kind == tokenize.DEDENT:
			depth -= 1
			continue
		if kind == tokenize.NEWLINE or (kind == tokenize.NL and not opened):
			if index < len(statements):
				yield depth, index, statements[index]
				index += 1
			opened = False
			continue
		if not opened and kind not in _SKIP:
			opened = True
	while index < len(statements):
		yield depth, index, statements[index]
		index += 1

def _aliases(resolved: list) -> dict:
	"""The local module names a file's uses reach through — D28's alias.

	A use of such a name is the callee's prefix followed by the attribute, so
	`helper.run` becomes `helper__run`. Only a local module import gets this; a
	non-local one is an ordinary rename (D20), because its attribute stays.
	"""
	found = {}
	for entry in resolved:
		if entry["kind"] != "module":
			continue
		for target in entry["targets"]:
			if not target["local"]:
				continue
			found[target["written"] if target["dotted"] else target["binds"]] = target["prefix"]
			if target["alias"] is None and not target["dotted"]:
				found[target["name"]] = target["prefix"]
	return found

def _imported(statement: dict, entry: dict, renames: dict):
	"""What an import statement becomes, or None when it is removed outright.

	D8 removes the statement of every inlined module; D20 says what is written in
	its place instead. A statement whose text is not only the import — a one-line
	compound, `if False: import helper` — keeps its header, because D22's `pass`
	clause is about the body a removal emptied, not about the header above it.

	**D33: a statement that would not move anything stands as the source wrote
	it.** The root's prefix is empty, so `renamed` is the identity there, and
	rebuilding the statement anyway produced `import time as time` and
	`email = email` — correct, lint-clean, and a bug to a reader. A statement
	with no local target and nothing to rename is returned untouched, which is
	also what keeps the source's own spacing.

	**The statement keeps its own indentation**, which the name-import case did
	not: a `from x import y` written inside a function came out at column 0, and
	the bundle did not parse.
	"""
	text = statement["text"]
	head = _CLAUSE.search(text)
	indent = statement["indent"]
	local = [target for target in entry["targets"] if target["local"]]
	other = [target for target in entry["targets"] if not target["local"]]
	if entry["kind"] == "star":
		if not local:
			return [text]
		return [f"{indent}{renames[name]} = {target['prefix']}{name}"
			for target in local for name in target.get("defined", [])]
	if entry["kind"] == "name":
		if not local:
			if not _moved(other, renames):
				return [text]
			spelled = [f"{target['name']} as {renames[target['binds']]}" for target in other]
			return _lines(statement, head, indent, f"from {entry['source']} import ", spelled)
		return [f"{indent}{renames[target['binds']]} = {target['prefix']}{target['name']}" for target in local]
	if not other:
		return [f"{_header(statement)} pass"] if head else None
	held = [target for target in other if target["dotted"] and target["alias"] is None]
	kept = [target for target in other if target not in held]
	if not local and not _moved(other, renames):
		return [text]
	names = [target["written"] for target in held]
	names += [f"{target['written']} as {renames[target['binds']]}" for target in kept]
	return _lines(statement, head, indent, "import ", names) + [
		f"{indent}{renames[target['binds']]} = {target['binds']}" for target in held if _moves(target, renames)]

def _moves(target: dict, renames: dict) -> bool:
	"""Whether this target's bound name is called something else in the bundle.

	D33's one comparison. It is false wherever the prefix is empty — the root, and
	only the root today — and true everywhere else, so a rebind whose two halves
	are the same name is not written.
	"""
	return renames[target["binds"]] != target["binds"]

def _moved(targets: list, renames: dict) -> bool:
	return any(_moves(target, renames) for target in targets)

def _lines(statement: dict, head, indent: str, opener: str, names: list) -> list:
	"""The emitted statement, or one statement per target — D32's two import rules.

	**No emitted import carries `, `**, so targets are joined with `,` whatever
	they are. **No emitted line carries both an alias and a comma**, so a statement
	with an aliased target puts each of its own on its own line, which is the
	shape the house rule asks for anyway (*aliased imports get their own line*,
	ruled 2026-09-09) — the bundler was breaking house style rather than inventing
	a form to satisfy a linter. Splitting cannot introduce a finding: a split
	aliased line clears the plain-import predecessor the check remembers.

	**A one-line compound cannot be split** — its body is one statement — so
	`if False: import a as A, b as B` keeps the comma. That is the one input where
	the two rules are not both satisfiable, and it is a shape almost nobody
	writes.
	"""
	if head is not None or not any(" as " in name for name in names):
		lead = f"{_header(statement)} " if head is not None else indent
		return [f"{lead}{opener}{','.join(names)}"]
	return [f"{indent}{opener}{name}" for name in names]

def _header(statement: dict) -> str:
	"""The compound header a one-line import sat on — `if False:` and the rest."""
	text = statement["text"]
	head = _CLAUSE.search(text)
	return text[:head.start()].rstrip() if head else ""

def _emptied(statement: dict, statements: list, index: int) -> list:
	"""What is left of a removed import — D22's `pass`, where the removal was the
	only statement of its block, and nothing at all otherwise.

	**A module-level import that was the file's last statement leaves nothing
	behind.** D32's third rule says removing a statement must not leave a double
	blank line, and a blank line left where the import was is one half of that
	pair — the other half is the blank the source wrote above it.
	"""
	indent = statement["indent"]
	if not indent or (index + 1 < len(statements) and statements[index + 1]["indent"] == indent):
		return [] if index + 1 < len(statements) or not indent else ["pass"]
	return [f"{indent}pass"]

def _blank_at(statements: list, index: int) -> bool:
	"""Whether the statement after `index` is a blank line — D32's third rule."""
	return index + 1 < len(statements) and not statements[index + 1]["text"].strip()

def _rewritten(text: str, renames: dict, aliases: dict, shadowed: set) -> list:
	"""The statement's text with the names that are ours moved and nothing else.

	A name an enclosing block has bound is that block's own and stays. A name
	after a dot belongs to whatever holds it, not to this file. A name a local
	module binds is its prefix instead, and the dot goes with it (D28).

	**A def's own parameter names stay too** — a parameter is a name the
	function binds, so R4 makes it the function's own. The body already knew
	that; the def line did not, and a parameter renamed there while the body
	kept the old name produced a `NameError` at the first call.

	Names are spliced in by position rather than rebuilt from tokens, because R7
	requires everything that is not a name to reach the bundle untouched and a
	rebuild decides the spacing for you.
	"""
	try:
		tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
	except (tokenize.TokenError, IndentationError):
		return [text]
	lines = text.splitlines(keepends=True)
	offsets, walked = [], 0
	for line in lines:
		offsets.append(walked)
		walked += len(line)
	edits = []
	after_dot = False
	own = _parameters_of(tokens)
	index = 0
	while index < len(tokens):
		token = tokens[index]
		index += 1
		if token[0] in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
			continue
		if token[0] != tokenize.NAME or keyword.iskeyword(token.string):
			after_dot = token.string == "."
			continue
		name = token.string
		start = offsets[token[2][0] - 1] + token[2][1]
		if after_dot or index - 1 in own:
			continue
		if (run := _dotted(name, tokens, index, aliases)) is not None:
			last = tokens[run[1] - 1]
			edits.append((start, offsets[last[3][0] - 1] + last[3][1], aliases[run[0]]))
			index = run[1]
			# The alias replaced the base *and* the dot, so the name that
			# follows is an attribute of whatever holds it — the same rule
			# the plain path already applies, and the one this path used
			# to skip past.
			after_dot = True
			continue
		if name in shadowed or name not in renames:
			continue
		edits.append((start, offsets[token[3][0] - 1] + token[3][1], renames[name]))
	for start, end, replacement in reversed(edits):
		text = text[:start] + replacement + text[end:]
	return text.split("\n")

def _parameters_of(tokens: list) -> set:
	"""Where a def's own parameter names are, among its tokens.

	A parameter is a name the function binds, so it is the function's own and
	is not translated (R4). **A default value and an annotation are not
	parameters**: they are read in the scope around the def, and are translated
	like any name there. So the parameter list is walked and a name counts only
	where a parameter can stand — right after the list's own `(` or a `,` at the
	list's level, or after a `*`.

	Nothing is returned for a statement that is not a def, and the positions are
	the token indices, so a caller can ask about a token it is holding.
	"""
	found = set()
	open_at = _parameters_open(tokens)
	if open_at is None:
		return found
	depth = 0
	previous = ""
	for at in range(open_at, len(tokens)):
		token = tokens[at]
		if token[0] == tokenize.OP:
			if token.string in "([{":
				depth += 1
			elif token.string in ")]}":
				depth -= 1
				if depth == 0:
					break
			previous = token.string if depth == 1 else ""
			continue
		if token[0] == tokenize.NAME and depth == 1 and previous in (",", "(", "*", "**"):
			found.add(at)
		previous = ""
	return found

def _parameters_open(tokens: list):
	"""The token index of the `(` that opens a def's parameter list, or None.

	The def's own name sits between the keyword and the bracket, so the bracket
	is found by walking past it rather than by counting.
	"""
	at = None
	for index, token in enumerate(tokens):
		if token[0] == tokenize.NAME and token.string == "def":
			at = index
			break
	if at is None:
		return None
	while at + 1 < len(tokens) and tokens[at + 1][0] != tokenize.OP:
		at += 1
	if at + 1 >= len(tokens) or tokens[at + 1][1] != "(":
		return None
	return at + 1

def _dotted(name: str, tokens: list, index: int, aliases: dict):
	"""The longest dotted run from here that a local module alias covers.

	`helper.run` matches on `helper`, and `sub.client.count` on `sub.client`, so
	the same rule reaches an attribute of an attribute without knowing how deep
	the import was written. Returns the alias key and where to carry on, or None.
	"""
	parts, at, longest = [name], index, None
	while at + 1 < len(tokens) and tokens[at][1] == "." and tokens[at + 1][0] == tokenize.NAME:
		parts.append(tokens[at + 1][1])
		at += 2
		if ".".join(parts) in aliases:
			# The prefix already ends in `__`, so the dot it replaces goes with it.
			longest = (".".join(parts), at + 1 if at < len(tokens) and tokens[at][1] == "." else at)
	if longest is not None:
		return longest
	if name in aliases and index < len(tokens) and tokens[index][1] == ".":
		return (name, index + 1)
	return None

def _bindings(body: str) -> tuple:
	"""The names a statement binds — its own block, and the block it opens.

	D2's list, plus the function-local import D20 adds. `global` and `nonlocal`
	bind nothing here: one names a module global and is renamed, the other
	belongs to an enclosing function and blocks (R4).
	"""
	if (head := _IMPORT.match(body)):
		return _imported_names(head), []
	if _ASSIGN.match(body):
		return [_ASSIGN.match(body).group(1)], []
	if (loop := _FOR.match(body)):
		return _TARGET.findall(loop.group(1)), []
	if body.startswith("def ") or body.startswith("async def "):
		return [_DEF_NAME.match(body).group(1)], _parameters(body)
	if body.startswith("class "):
		return [body[len("class "):].split("(")[0].split(":")[0].strip()], []
	return _AS.findall(body) + _WALRUS.findall(body), []

def _imported_names(head) -> list:
	"""The names a function-local import binds in its own block (D2, D20)."""
	if head.group("module") is not None:
		return [part.strip().split(" as ")[-1].split(".")[0] for part in head.group("module").split(",")]
	return [part.strip().split(" as ")[-1] for part in head.group("names").split(",") if part.strip() != "*"]

def _parameters(body: str) -> list:
	"""A def's parameter names, which bind inside the body it opens."""
	open_at = body.find("(")
	if open_at < 0:
		return []
	depth = 0
	for index in range(open_at, len(body)):
		if body[index] == "(":
			depth += 1
		elif body[index] == ")":
			depth -= 1
			if not depth:
				inner = body[open_at + 1:index]
				break
	else:
		return []
	found = []
	for part in _split(inner):
		name = part.split(":")[0].split("=")[0].strip().lstrip("*")
		if match := _NAMED.fullmatch(name.strip()):
			found.append(match.group())
	return found

def _split(text: str) -> list:
	"""The text's top-level commas, so a default holding one is not a split."""
	parts, depth, current = [], 0, ""
	for character in text:
		if character in "([{":
			depth += 1
		elif character in ")]}":
			depth -= 1
		if character == "," and not depth:
			parts.append(current)
			current = ""
			continue
		current += character
	parts.append(current)
	return parts
