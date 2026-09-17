import ast,io,os,re,token,tokenize

SPECIAL = {"True","False","None","__name__","__doc__","__package__","__file__"}

#: Single-name imports with no alias: the only form merge_imports can unpack.
_MERGE_IMPORT = re.compile(r"^import ([A-Za-z_][A-Za-z0-9_]*)$")
_MERGE_FROM = re.compile(r"^from ([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*) import ([A-Za-z_][A-Za-z0-9_]*)$")

class Context:
	def __init__(self, root):
		self.root = root
		self.mods = {}
		self.entry = None
		self.warnings = []

class Mod:
	def __init__(self, modpath, file):
		self.modpath = modpath
		self.flat = modpath.replace(".", "_")
		self.file = file
		self.is_pkg = os.path.basename(file) == "__init__.py"
		self.rel = ""
		self.tokens = []
		self.tree = None
		self.line_offsets = []
		self.topvals = {}
		self.bindmap = {}
		self.depmods = {}
		self.imports_at = {}
		self.namespace = {}
		self.ownrefs = {}
		self.defkw = {}
		self.strips_at = {}
		self.globals_at = {}

class Scope:
	"""One level on the scope stack: locals, globals, nonlocals, and imports."""
	def __init__(self, kind, locals_, globals_=None, nonlocals_=None, imports_=None):
		self.kind = kind
		self.locals = locals_
		self.globals = globals_ or {}
		self.nonlocals = nonlocals_ or {}
		self.imports = imports_ or {}

def _read_text(path):
	with open(path, "rb") as f:
		raw = f.read()
	try:
		return raw.decode("utf-8")
	except UnicodeDecodeError:
		return raw.decode("latin-1")

def _tokenize_text(text):
	return list(tokenize.generate_tokens(io.StringIO(text).readline))

def _line_offsets(text):
	"""Return the character offset where each line of `text` starts.

	Index by (line_number) with line numbers counting from 1, so
	`line_offsets(lineno - 1)` is the offset of the line's first column.
	"""
	res = [0]
	for i, ch in enumerate(text):
		if ch == "\n":
			res.append(i + 1)
	return res

def _merge_imports(lines):
	merged = []
	plain = []
	froms = {}
	def emit_buf():
		if plain:
			merged.append("import " + ",".join(plain))
			plain.clear()
		for mod, names in froms.items():
			merged.append(f"from {mod} import {','.join(names)}")
		froms.clear()
	def emit(line):
		emit_buf()
		merged.append(line)
	for line in lines:
		m = _MERGE_IMPORT.match(line)
		if m is not None:
			plain.append(m.group(1))
			continue
		f = _MERGE_FROM.match(line)
		if f is not None:
			froms.setdefault(f.group(1), []).append(f.group(2))
			continue
		emit(line)
	emit_buf()
	return merged

def _token_index_at(toks, pos):
	for i, t in enumerate(toks):
		if (t.start[0], t.start[1]) == pos:
			return i
	return None

def _store_target_names(node):
	"""Return the names that are being assigned to in a target node."""
	res = {}
	if isinstance(node, ast.Name):
		res[node.id] = True
	elif isinstance(node, (ast.Tuple, ast.List)):
		for e in node.elts:
			res.update(_store_target_names(e))
	elif isinstance(node, ast.Starred):
		res.update(_store_target_names(node.value))
	return res

# ---------- locating ----------

def _locate(ctx, dotted):
	segs = dotted.split(".")
	dirpath = ctx.root
	parts = []
	for idx, seg in enumerate(segs):
		sub = os.path.join(dirpath, seg)
		if os.path.isfile(os.path.join(sub, "__init__.py")):
			dirpath = sub
			parts.append(seg)
			continue
		if os.path.isfile(sub + ".py"):
			if idx != len(segs) - 1:
				return None
			parts.append(seg)
			return ".".join(parts), sub + ".py"
		return None
	if not parts:
		return None
	return ".".join(parts), os.path.join(dirpath, "__init__.py")

def _ensure(ctx, dotted):
	if not dotted:
		return None
	res = _locate(ctx, dotted)
	if res is None:
		return None
	modpath, file = res
	m = ctx.mods.get(modpath)
	if m is not None:
		return m
	m = Mod(modpath, file)
	ctx.mods[modpath] = m
	m.rel = os.path.relpath(file, ctx.root)
	m.text = _read_text(file)
	m.line_offsets = _line_offsets(m.text)
	m.tokens = _tokenize_text(m.text)
	try:
		m.tree = ast.parse(m.text)
	except SyntaxError:
		m.tree = None
	_analyze(ctx, m)
	return m

def _ensure_prefixes(ctx, dotted):
	segs = dotted.split(".")
	out = []
	for i in range(1, len(segs) + 1):
		m = _ensure(ctx, ".".join(segs[:i]))
		if m is None:
			break
		out.append(m)
	return out

# ---------- analyzing ----------

def _analyze(ctx, m):
	if m.tree is None:
		return
	local_defs, gl, nl, imp = _scope_frame(m, m.tree)
	m.topvals = local_defs.copy()
	for name in imp:
		m.topvals.pop(name, None)
	_resolve_imports(ctx, m)
	m.namespace = {}
	for name, (kind, target) in m.bindmap.items():
		m.namespace[name] = "mod" if kind == "mod" else "value"
	for name in m.topvals:
		if name not in m.namespace:
			m.namespace[name] = "value"
	_classify(m)
	_defkw_of(m)

def _scope_frame(m, node):
	local_defs = {}
	gl = {}
	nl = {}
	imp = {}
	def add(names):
		for n in names:
			if n not in gl and n not in nl:
				local_defs[n] = True
	stack = [node]
	while stack:
		n = stack.pop()
		for c in ast.iter_child_nodes(n):
			if isinstance(c, ast.Global):
				gl.update(dict.fromkeys(c.names))
				continue
			if isinstance(c, ast.Nonlocal):
				nl.update(dict.fromkeys(c.names))
				continue
			if isinstance(c, ast.Import):
				for a in c.names:
					b = a.asname or a.name.split(".")[0]
					imp[b] = True
					add([b])
				continue
			if isinstance(c, ast.ImportFrom):
				for a in c.names:
					if a.name != "*":
						b = a.asname or a.name
						imp[b] = True
						add([b])
				continue
			if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
				add([c.name])
				continue
			if isinstance(c, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
			                  ast.GeneratorExp)):
				continue
			if isinstance(c, ast.Assign):
				for t in c.targets:
					add(_store_target_names(t))
				continue
			if isinstance(c, ast.AnnAssign):
				add(_store_target_names(c.target))
				continue
			if isinstance(c, ast.AugAssign):
				add(_store_target_names(c.target))
				continue
			if isinstance(c, ast.NamedExpr):
				add(_store_target_names(c.target))
				continue
			if isinstance(c, (ast.For, ast.AsyncFor)):
				add(_store_target_names(c.target))
				continue
			if isinstance(c, (ast.With, ast.AsyncWith)):
				for item in c.items:
					if item.optional_vars is not None:
						add(_store_target_names(item.optional_vars))
				continue
			if isinstance(c, ast.ExceptHandler) and c.name:
				add([c.name])
				continue
			stack.append(c)
	return local_defs, gl, nl, imp

def _resolve_imports(ctx, m):
	if m.tree is None:
		return
	for node in ast.walk(m.tree):
		if isinstance(node, ast.Import):
			_import_stmt(ctx, m, node)
		elif isinstance(node, ast.ImportFrom):
			_from_stmt(ctx, m, node)

def _import_stmt(ctx, m, node):
	local_hit = False
	ext = []
	for a in node.names:
		first = a.name.split(".")[0]
		mfound = _ensure(ctx, first)
		prefixes = _ensure_prefixes(ctx, a.name)
		if mfound is None:
			ext.append(_canon_import(a))
			continue
		local_hit = True
		if a.asname:
			full = _ensure(ctx, a.name)
			target = full if full is not None else mfound
			m.bindmap[a.asname] = ("mod", target)
			m.depmods[target.modpath] = target
		else:
			m.bindmap[first] = ("mod", mfound)
			m.depmods[mfound.modpath] = mfound
		for p in prefixes:
			m.depmods[p.modpath] = p
	_put_statement(m, node, local_hit, ext)

def _from_stmt(ctx, m, node):
	base = _base_of(m, node)
	bmod = _ensure(ctx, base)
	local_hit = False
	ext = []
	for a in node.names:
		if a.name == "*":
			ctx.warnings.append("%s:%d star import kept as-is" % (m.modpath or "entry", node.lineno))
			ext.append(_canon_from(a, base, node))
			continue
		if bmod is None:
			ext.append(_canon_from(a, base, node))
			continue
		child = _ensure(ctx, bmod.modpath + "." + a.name)
		kind = bmod.namespace.get(a.name)
		bindname = a.asname or a.name
		if child is not None and kind != "value":
			m.bindmap[bindname] = ("mod", child)
			m.depmods[child.modpath] = child
		else:
			m.bindmap[bindname] = ("name", bmod.flat + "_" + a.name)
			m.depmods[bmod.modpath] = bmod
		local_hit = True
	_put_statement(m, node, local_hit, ext)

def _base_of(m, node):
	if node.level == 0:
		return node.module or ""
	pkg = m.modpath if m.is_pkg else (m.modpath.rsplit(".", 1)[0] if "." in m.modpath else "")
	base = pkg
	for _ in range(node.level - 1):
		base = base.rsplit(".", 1)[0] if "." in base else ""
	if node.module:
		base = (base + "." + node.module) if base else node.module
	return base

def _put_statement(m, node, local_hit, ext):
	toplev = node.col_offset == 0
	strip = local_hit or toplev
	if not strip:
		ext = []
	m.imports_at[(node.lineno, node.col_offset)] = (strip, ext)

def _canon_import(a):
	name = a.name + (" as " + a.asname if a.asname else "")
	return "import " + name

def _canon_from(a, base, node):
	name = a.name + (" as " + a.asname if a.asname else "")
	prefix = "." * node.level
	mod = (prefix + base) if base else prefix
	return "from " + mod + " import " + name

# ---------- classifying ----------

def _params_of(node):
	st = {}
	for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
		st[a.arg] = True
	if node.args.vararg:
		st[node.args.vararg.arg] = True
	if node.args.kwarg:
		st[node.args.kwarg.arg] = True
	return st

def _classify(m):
	_walk(m, m.tree, [m])

def _walk(m, node, stack):
	if node is None:
		return
	if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
		for d in node.decorator_list:
			_walk(m, d, stack)
		_walk(m, node.args, stack)
		local_defs, gl, nl, imp = _scope_frame(m, node)
		local_defs.update(_params_of(node))
		stack.append(Scope("func", local_defs, gl, nl, imp))
		for c in node.body:
			_walk(m, c, stack)
		stack.pop()
		return
	if isinstance(node, ast.Lambda):
		stack.append(Scope("lambda", _params_of(node)))
		_walk(m, node.body, stack)
		stack.pop()
		return
	if isinstance(node, ast.Assign) and _strip_selfalias(m, node, stack):
		return
	if isinstance(node, ast.ClassDef):
		for b in node.bases:
			_walk(m, b, stack)
		for k in node.keywords:
			_walk(m, k.value, stack)
		for d in node.decorator_list:
			_walk(m, d, stack)
		local_defs, gl, nl, imp = _scope_frame(m, node)
		stack.append(Scope("class", local_defs))
		for c in node.body:
			_walk(m, c, stack)
		stack.pop()
		return
	if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
		gens = node.generators
		if not gens:
			return
		_walk(m, gens[0].iter, stack)
		locals_ = {}
		for g in gens:
			locals_.update(_store_target_names(g.target))
		stack.append(Scope("comp", locals_))
		for g in gens:
			if g is not gens[0]:
				_walk(m, g.iter, stack)
			for cond in g.ifs:
				_walk(m, cond, stack)
			_walk(m, g.target, stack)
		if isinstance(node, ast.DictComp):
			_walk(m, node.key, stack)
			_walk(m, node.value, stack)
		else:
			_walk(m, node.elt, stack)
		stack.pop()
		return
	if isinstance(node, ast.Name):
		_name_ref(m, node, stack)
		return
	if isinstance(node, ast.Global):
		_global_stmt(m, node, stack)
		return
	if isinstance(node, ast.comprehension):
		return
	for c in ast.iter_child_nodes(node):
		_walk(m, c, stack)

def _global_stmt(m, node, stack):
	if not m.flat:
		return
	for name in node.names:
		if name not in m.topvals and name not in m.bindmap:
			continue
		bm, shadowed = _resolve(m, name, stack)
		if bm is None:
			continue
		key = m.flat + "_" + name
		m.globals_at.setdefault(node.lineno, {})[name] = key

def _strip_selfalias(m, node, stack):
	if len(node.targets) != 1:
		return False
	t = node.targets[0]
	if not (isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store)):
		return False
	v = node.value
	if not (isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load)):
		return False
	bm, shadowed = _resolve(m, v.id, stack)
	if shadowed or bm is None or bm[0] != "mod":
		return False
	m.strips_at[(node.lineno, node.col_offset)] = True
	return True

def _resolve(m, name, stack):
	shadowed = False
	for f in reversed(stack):
		if f is m:
			break
		if f.kind in ("func", "lambda", "comp"):
			if name in f.globals:
				continue
			if name in f.nonlocals or name in f.locals:
				if name not in f.imports:
					shadowed = True
					break
			continue
		if f.kind == "class" and stack[-1] is f and name in f.locals:
			shadowed = True
			break
	if shadowed:
		return None, True
	b = m.bindmap.get(name)
	if b is not None:
		return b, False
	if name in m.topvals:
		return (("value", m.flat + "_" + name) if m.flat else ("value", name)), False
	return None, False

def _name_ref(m, node, stack):
	name = node.id
	if name in SPECIAL:
		return
	pos = (node.lineno, node.col_offset)
	store = isinstance(node.ctx, ast.Store)
	bm, shadowed = _resolve(m, name, stack)
	if shadowed:
		return
	if bm is not None:
		kind, target = bm
		if kind == "mod":
			if store and m.flat:
				m.ownrefs[pos] = ("x", m.flat + "_" + name)
				m.topvals[name] = True
				return
			m.ownrefs[pos] = ("M", target)
		else:
			m.ownrefs[pos] = ("x", target)
		return
	if store and m.flat:
		m.ownrefs[pos] = ("x", m.flat + "_" + name)
		m.topvals[name] = True

def _defkw_of(m):
	if not m.flat:
		return
	moddefs = set()
	for node in m.tree.body:
		if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
			moddefs.add(node)
	kwmap = {}
	for i, t in enumerate(m.tokens):
		if t.type == token.NAME and t.string in ("def", "class"):
			if i + 1 < len(m.tokens) and m.tokens[i + 1].type == token.NAME:
				kwmap[(t.start[0], t.start[1])] = m.tokens[i + 1].string
	for node in ast.walk(m.tree):
		if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
			continue
		if node not in moddefs:
			continue
		if node.name not in m.topvals:
			continue
		key = (node.lineno, node.col_offset)
		if kwmap.get(key) != node.name:
			key = None
			for k, nm in kwmap.items():
				if nm == node.name and k[0] == node.lineno:
					key = k
					break
		if key is not None:
			m.defkw[key] = m.flat + "_" + node.name

# ---------- rewriting ----------

def _on(m, start, end):
	return m.line_offsets[start[0] - 1] + start[1], m.line_offsets[end[0] - 1] + end[1]

def _strip_stmt(m, toks, i, reps):
	n = len(toks)
	j = i
	endtok = None
	depth = 0
	while j < n:
		tj = toks[j]
		if tj.type == tokenize.NEWLINE:
			endtok = tj
			break
		if tj.type == token.OP:
			if tj.string == "(":
				depth += 1
			elif tj.string == ")":
				depth -= 1
			elif tj.string == ";" and depth == 0:
				endtok = tj
				break
		j += 1
	if endtok is None:
		endtok = toks[n - 1]
	t = toks[i]
	s, e = _on(m, t.start, endtok.end)
	if endtok.type == tokenize.NEWLINE:
		s = m.line_offsets[t.start[0] - 1]
	elif endtok.string == ";":
		while e < len(m.text) and m.text[e] == " ":
			e += 1
	reps.append((s, e, ""))
	return j + 1

def _rewrite(ctx, m):
	toks = m.tokens
	reps = []
	at_stmt = True
	pending = None
	skip_until = None
	n = len(toks)
	i = 0
	while i < n:
		t = toks[i]
		if skip_until is not None and i <= skip_until:
			i += 1
			continue
		k = t.type
		s = t.string
		if k == tokenize.NEWLINE:
			at_stmt = True
			i += 1
			continue
		if k == tokenize.DEDENT:
			at_stmt = True
			i += 1
			continue
		if k == token.OP and s == ";":
			at_stmt = True
			i += 1
			continue
		if k != token.NAME:
			i += 1
			continue
		if pending is not None and pending[0] == i:
			start, end = _on(m, t.start, t.end)
			reps.append((start, end, pending[1]))
			pending = None
			at_stmt = False
			i += 1
			continue
		if at_stmt and s in ("import", "from"):
			info = m.imports_at.get((t.start[0], t.start[1]))
			if info is not None and info[0]:
				i = _strip_stmt(m, toks, i, reps)
				at_stmt = True
				continue
		if at_stmt and (t.start[0], t.start[1]) in m.strips_at:
			i = _strip_stmt(m, toks, i, reps)
			at_stmt = True
			continue
		if s in ("def", "class"):
			repl = m.defkw.get((t.start[0], t.start[1]))
			if repl is not None and i + 1 < n and toks[i + 1].type == token.NAME:
				pending = (i + 1, repl)
			at_stmt = False
			i += 1
			continue
		if s == "global" and at_stmt:
			gmap = m.globals_at.get(t.start[0])
			if gmap:
				cur = i + 1
				out = []
				while cur < n and toks[cur].type == token.NAME:
					gname = toks[cur].string
					if gname in gmap:
						out.append((cur, gmap[gname]))
					cur += 2
				for cidx, repltext in out:
					cs, ce = _on(m, toks[cidx].start, toks[cidx].end)
					reps.append((cs, ce, repltext))
				i = cur if cur < n else n
				at_stmt = False
				continue
		ent = m.ownrefs.get((t.start[0], t.start[1]))
		if ent is None:
			at_stmt = False
			i += 1
			continue
		k2, tgt = ent
		start, end = _on(m, t.start, t.end)
		if k2 == "x":
			reps.append((start, end, tgt))
			at_stmt = False
			i += 1
			continue
		chain = _gather_chain(toks, i)
		if len(chain) <= 1:
			ctx.warnings.append("module used as value at %s:%d" % (m.rel, t.start[0]))
			at_stmt = False
			i += 1
			continue
		folded = _fold(ctx, tgt, chain)
		if folded is None:
			ctx.warnings.append("unresolved chain at %s:%d" % (m.rel, t.start[0]))
			at_stmt = False
			i += 1
			continue
		text, consumed, owner = folded
		base = toks[chain[0][0]]
		last = toks[chain[consumed - 1][0]]
		bsp, bep = _on(m, base.start, last.end)
		reps.append((bsp, bep, text))
		skip_until = chain[consumed - 1][0]
		at_stmt = False
		i += 1
	reps.sort(key=lambda r: r[0])
	out = []
	last = 0
	for s, e, new in reps:
		if s < last:
			continue
		out.append(m.text[last:s])
		out.append(new)
		last = e
	out.append(m.text[last:])
	return "".join(out)

def _gather_chain(toks, i):
	chain = []
	cursor = i
	while cursor < len(toks) and toks[cursor].type == token.NAME:
		chain.append((cursor, toks[cursor].string))
		if (cursor + 2 < len(toks) and toks[cursor + 1].type == token.OP
		        and toks[cursor + 1].string == "." and toks[cursor + 2].type == token.NAME):
			cursor += 2
		else:
			break
	return chain

def _fold(ctx, target, chain):
	cur = target
	prefix = cur.flat
	consumed = 1
	for k in range(1, len(chain)):
		seg = chain[k][1]
		kind = cur.namespace.get(seg)
		if kind == "value":
			return prefix + "_" + seg, k + 1, cur
		child = ctx.mods.get(cur.modpath + "." + seg)
		if child is None:
			return None
		cur = child
		prefix += "_" + seg
		consumed = k + 1
	return prefix, consumed, cur

# ---------- ordering ----------

def _topo(ctx):
	order = []
	visiting = {}
	done = {}
	def visit(m):
		if m in done or m in visiting:
			return
		visiting[m] = True
		for d in m.depmods.values():
			if d is not ctx.entry:
				visit(d)
		visiting.pop(m, None)
		done[m] = True
		order.append(m)
	for d in ctx.entry.depmods.values():
		if d is not ctx.entry:
			visit(d)
	return order
