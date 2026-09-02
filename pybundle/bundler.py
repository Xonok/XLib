import argparse,ast,io,os,re,sys,token,tokenize

SPECIAL = {"True","False","None","__name__","__doc__","__package__","__file__"}

def read_text(path):
	with open(path, "rb") as f:
		raw = f.read()
	try:
		return raw.decode("utf-8")
	except UnicodeDecodeError:
		return raw.decode("latin-1")

def tokenize_text(text):
	return list(tokenize.generate_tokens(io.StringIO(text).readline))

def line_lengths(text):
	res = [0]
	for i, ch in enumerate(text):
		if ch == "\n":
			res.append(i + 1)
	return res

_PLAIN_IMPORT = re.compile(r"^import ([A-Za-z_][A-Za-z0-9_]*)$")
_PLAIN_FROM = re.compile(r"^from ([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*) import ([A-Za-z_][A-Za-z0-9_]*)$")

def merge_imports(lines):
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
		m = _PLAIN_IMPORT.match(line)
		if m is not None:
			plain.append(m.group(1))
			continue
		f = _PLAIN_FROM.match(line)
		if f is not None:
			froms.setdefault(f.group(1), []).append(f.group(2))
			continue
		emit(line)
	emit_buf()
	return merged

def token_index_at(toks, pos):
	for i, t in enumerate(toks):
		if (t.start[0], t.start[1]) == pos:
			return i
	return None

def target_names(node):
	res = {}
	if isinstance(node, ast.Name):
		res[node.id] = True
	elif isinstance(node, (ast.Tuple, ast.List)):
		for e in node.elts:
			res.update(target_names(e))
	elif isinstance(node, ast.Starred):
		res.update(target_names(node.value))
	return res

class Mod:
	def __init__(self, modpath, file):
		self.modpath = modpath
		self.flat = modpath.replace(".", "_")
		self.file = file
		self.is_pkg = os.path.basename(file) == "__init__.py"
		self.rel = ""
		self.tokens = []
		self.tree = None
		self.lines = []
		self.topvals = {}
		self.bindmap = {}
		self.depmods = {}
		self.imports_at = {}
		self.namespace = {}
		self.ownrefs = {}
		self.defkw = {}
		self.strips_at = {}
		self.refdeps = {}
		self.globals_at = {}

class Frame:
	def __init__(self, kind, locals_, globals_=None, nonlocals_=None, imports_=None):
		self.kind = kind
		self.locals = locals_
		self.globals = globals_ or {}
		self.nonlocals = nonlocals_ or {}
		self.imports = imports_ or {}

class Bundler:
	def __init__(self):
		self.root = ""
		self.mods = {}
		self.entry = None
		self.warnings = []

	def locate(self, dotted):
		segs = dotted.split(".")
		dirpath = self.root
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

	def ensure(self, dotted):
		if not dotted:
			return None
		res = self.locate(dotted)
		if res is None:
			return None
		modpath, file = res
		m = self.mods.get(modpath)
		if m is None:
			m = Mod(modpath, file)
			self.mods[modpath] = m
			m.rel = os.path.relpath(file, self.root)
			m.text = read_text(file)
			m.lines = line_lengths(m.text)
			m.tokens = tokenize_text(m.text)
			try:
				m.tree = ast.parse(m.text)
			except SyntaxError:
				m.tree = None
			self.analyze(m)
		return m

	def analyze(self, m):
		if m.tree is None:
			return
		st, gl, nl, imp = self.scope_frame(m, m.tree)
		m.topvals = st.copy()
		for name in imp:
			m.topvals.pop(name, None)
		self.resolve_imports(m)
		m.namespace = {}
		for name, (kind, target) in m.bindmap.items():
			m.namespace[name] = "mod" if kind == "mod" else "value"
		for name in m.topvals:
			if name not in m.namespace:
				m.namespace[name] = "value"
		self.classify(m)
		self.defkw_of(m)

	def scope_frame(self, m, node):
		st = {}
		gl = {}
		nl = {}
		imp = {}
		def add(names):
			for n in names:
				if n not in gl and n not in nl:
					st[n] = True
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
						add(target_names(t))
					continue
				if isinstance(c, ast.AnnAssign):
					add(target_names(c.target))
					continue
				if isinstance(c, ast.AugAssign):
					add(target_names(c.target))
					continue
				if isinstance(c, ast.NamedExpr):
					add(target_names(c.target))
					continue
				if isinstance(c, (ast.For, ast.AsyncFor)):
					add(target_names(c.target))
					continue
				if isinstance(c, (ast.With, ast.AsyncWith)):
					for item in c.items:
						if item.optional_vars is not None:
							add(target_names(item.optional_vars))
					continue
				if isinstance(c, ast.ExceptHandler) and c.name:
					add([c.name])
					continue
				stack.append(c)
		return st, gl, nl, imp

	def resolve_imports(self, m):
		if m.tree is None:
			return
		for node in ast.walk(m.tree):
			if isinstance(node, ast.Import):
				self.import_stmt(m, node)
			elif isinstance(node, ast.ImportFrom):
				self.from_stmt(m, node)

	def import_stmt(self, m, node):
		local_hit = False
		ext = []
		for a in node.names:
			first = a.name.split(".")[0]
			mfound = self.ensure(first)
			prefixes = self.ensure_prefixes(a.name)
			if mfound is None:
				ext.append(self.canon_import(a))
				continue
			local_hit = True
			if a.asname:
				full = self.ensure(a.name)
				target = full if full is not None else mfound
				m.bindmap[a.asname] = ("mod", target)
				m.depmods[target.modpath] = target
			else:
				m.bindmap[first] = ("mod", mfound)
				m.depmods[mfound.modpath] = mfound
			for p in prefixes:
				m.depmods[p.modpath] = p
		self.put_statement(m, node, local_hit, ext)

	def from_stmt(self, m, node):
		base = self.base_of(m, node)
		bmod = self.ensure(base)
		local_hit = False
		ext = []
		for a in node.names:
			if a.name == "*":
				self.warnings.append("%s:%d star import kept as-is" % (m.modpath or "entry", node.lineno))
				ext.append(self.canon_from(a, base, node))
				continue
			if bmod is None:
				ext.append(self.canon_from(a, base, node))
				continue
			child = self.ensure(bmod.modpath + "." + a.name)
			kind = bmod.namespace.get(a.name)
			bindname = a.asname or a.name
			if child is not None and kind != "value":
				m.bindmap[bindname] = ("mod", child)
				m.depmods[child.modpath] = child
			else:
				m.bindmap[bindname] = ("name", bmod.flat + "_" + a.name)
				m.depmods[bmod.modpath] = bmod
			local_hit = True
		self.put_statement(m, node, local_hit, ext)

	def base_of(self, m, node):
		if node.level == 0:
			return node.module or ""
		pkg = m.modpath if m.is_pkg else m.modpath.rsplit(".", 1)[0] if m.modpath else ""
		base = pkg
		for _ in range(node.level - 1):
			base = base.rsplit(".", 1)[0] if "." in base else ""
		if node.module:
			base = (base + "." + node.module) if base else node.module
		return base

	def put_statement(self, m, node, local_hit, ext):
		toplev = node.col_offset == 0
		strip = local_hit or toplev
		if not strip:
			ext = []
		m.imports_at[(node.lineno, node.col_offset)] = (strip, ext)

	def canon_import(self, a):
		name = a.name + (" as " + a.asname if a.asname else "")
		return "import " + name

	def canon_from(self, a, base, node):
		name = a.name + (" as " + a.asname if a.asname else "")
		prefix = "." * node.level
		mod = (prefix + base) if base else prefix
		return "from " + mod + " import " + name

	def ensure_prefixes(self, dotted):
		segs = dotted.split(".")
		out = []
		for i in range(1, len(segs) + 1):
			m = self.ensure(".".join(segs[:i]))
			if m is None:
				break
			out.append(m)
		return out

	# ---------- scoping ----------

	def params_of(self, node):
		st = {}
		for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
			st[a.arg] = True
		if node.args.vararg:
			st[node.args.vararg.arg] = True
		if node.args.kwarg:
			st[node.args.kwarg.arg] = True
		return st

	def classify(self, m):
		self.walk(m, m.tree, [m])

	def walk(self, m, node, stack):
		if node is None:
			return
		if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
			for d in node.decorator_list:
				self.walk(m, d, stack)
			self.walk(m, node.args, stack)
			st, gl, nl, imp = self.scope_frame(m, node)
			st.update(self.params_of(node))
			stack.append(Frame("func", st, gl, nl, imp))
			for c in node.body:
				self.walk(m, c, stack)
			stack.pop()
			return
		if isinstance(node, ast.Lambda):
			stack.append(Frame("lambda", self.params_of(node)))
			self.walk(m, node.body, stack)
			stack.pop()
			return
		if isinstance(node, ast.Assign) and self.strip_selfalias(m, node, stack):
			return
		if isinstance(node, ast.ClassDef):
			for b in node.bases:
				self.walk(m, b, stack)
			for k in node.keywords:
				self.walk(m, k.value, stack)
			for d in node.decorator_list:
				self.walk(m, d, stack)
			st, gl, nl, imp = self.scope_frame(m, node)
			stack.append(Frame("class", st))
			for c in node.body:
				self.walk(m, c, stack)
			stack.pop()
			return
		if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
			gens = node.generators
			if not gens:
				return
			self.walk(m, gens[0].iter, stack)
			locals_ = {}
			for g in gens:
				locals_.update(target_names(g.target))
			stack.append(Frame("comp", locals_))
			for g in gens:
				if g is not gens[0]:
					self.walk(m, g.iter, stack)
				for cond in g.ifs:
					self.walk(m, cond, stack)
				self.walk(m, g.target, stack)
			if isinstance(node, ast.DictComp):
				self.walk(m, node.key, stack)
				self.walk(m, node.value, stack)
			else:
				self.walk(m, node.elt, stack)
			stack.pop()
			return
		if isinstance(node, ast.Name):
			self.name_ref(m, node, stack)
			return
		if isinstance(node, ast.Global):
			self.global_stmt(m, node, stack)
			return
		if isinstance(node, ast.comprehension):
			return
		for c in ast.iter_child_nodes(node):
			self.walk(m, c, stack)

	def global_stmt(self, m, node, stack):
		if not m.flat:
			return
		for name in node.names:
			if name not in m.topvals and name not in m.bindmap:
				continue
			bm, shadowed = self.resolve(m, name, stack)
			if bm is None:
				continue
			key = m.flat + "_" + name
			m.globals_at.setdefault(node.lineno, {})[name] = key

	def strip_selfalias(self, m, node, stack):
		if len(node.targets) != 1:
			return False
		t = node.targets[0]
		if not (isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store)):
			return False
		v = node.value
		if not (isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load)):
			return False
		bm, shadowed = self.resolve(m, v.id, stack)
		if shadowed or bm is None or bm[0] != "mod":
			return False
		m.strips_at[(node.lineno, node.col_offset)] = True
		return True

	def resolve(self, m, name, stack):
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

	def name_ref(self, m, node, stack):
		name = node.id
		if name in SPECIAL:
			return
		pos = (node.lineno, node.col_offset)
		store = isinstance(node.ctx, ast.Store)
		bm, shadowed = self.resolve(m, name, stack)
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

	def defkw_of(self, m):
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

	def on(self, m, start, end):
		return m.lines[start[0] - 1] + start[1], m.lines[end[0] - 1] + end[1]

	def strip_stmt(self, m, toks, i, reps):
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
		s, e = self.on(m, t.start, endtok.end)
		if endtok.type == tokenize.NEWLINE:
			s = m.lines[t.start[0] - 1]
		elif endtok.string == ";":
			while e < len(m.text) and m.text[e] == " ":
				e += 1
		reps.append((s, e, ""))
		return j + 1

	def rewrite(self, m):
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
				start, end = self.on(m, t.start, t.end)
				reps.append((start, end, pending[1]))
				pending = None
				at_stmt = False
				i += 1
				continue
			if at_stmt and s in ("import", "from"):
				info = m.imports_at.get((t.start[0], t.start[1]))
				if info is not None and info[0]:
					i = self.strip_stmt(m, toks, i, reps)
					at_stmt = True
					continue
			if at_stmt and (t.start[0], t.start[1]) in m.strips_at:
				i = self.strip_stmt(m, toks, i, reps)
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
						cs, ce = self.on(m, toks[cidx].start, toks[cidx].end)
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
			start, end = self.on(m, t.start, t.end)
			if k2 == "x":
				reps.append((start, end, tgt))
				at_stmt = False
				i += 1
				continue
			chain = self.gather_chain(toks, i)
			if len(chain) <= 1:
				self.warnings.append("module used as value at %s:%d" % (m.rel, t.start[0]))
				at_stmt = False
				i += 1
				continue
			folded = self.fold(tgt, chain)
			if folded is None:
				self.warnings.append("unresolved chain at %s:%d" % (m.rel, t.start[0]))
				at_stmt = False
				i += 1
				continue
			text, consumed, owner = folded
			base = toks[chain[0][0]]
			last = toks[chain[consumed - 1][0]]
			bsp, bep = self.on(m, base.start, last.end)
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

	def gather_chain(self, toks, i):
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

	def disk_child(self, modpath, seg):
		m = self.mods.get(modpath)
		if m is None:
			return False
		sub = os.path.join(os.path.dirname(m.file), seg)
		return os.path.isfile(sub + ".py") or os.path.isfile(os.path.join(sub, "__init__.py"))

	def toplvl_deps(self, m):
		def scan(node):
			if node is None:
				return
			if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
				return
			if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
				return
			if isinstance(node, ast.Name):
				if node.id in SPECIAL or not isinstance(node.ctx, ast.Load):
					return
				bm, shadowed = self.resolve(m, node.id, [m])
				if shadowed or bm is None or bm[0] != "mod":
					return
				pos = (node.lineno, node.col_offset)
				owner = self.owner_of(m, bm[1], pos)
				if owner is not None and owner is not m:
					m.refdeps[owner] = owner
				return
			for c in ast.iter_child_nodes(node):
				scan(c)
		for st in m.tree.body:
			scan(st)

	def owner_of(self, m, target, pos):
		chain = self.gather_chain(m.tokens, token_index_at(m.tokens, pos))
		if len(chain) <= 1:
			return None
		folded = self.fold(target, chain)
		if folded is None:
			return None
		return folded[2]

	def fold(self, target, chain):
		cur = target
		prefix = cur.flat
		consumed = 1
		for k in range(1, len(chain)):
			seg = chain[k][1]
			kind = cur.namespace.get(seg)
			if kind == "value":
				prefix += "_" + seg
				consumed = k + 1
				return prefix, consumed, cur
			if kind == "mod":
				child = self.mods.get(cur.modpath + "." + seg)
				if child is None:
					return None
				cur = child
				prefix += "_" + seg
				consumed = k + 1
				continue
			child = self.mods.get(cur.modpath + "." + seg)
			if child is not None or self.disk_child(cur.modpath, seg):
				if child is not None:
					cur = child
				prefix += "_" + seg
				consumed = k + 1
				continue
			return None
		return prefix, consumed, cur

	# ---------- ordering & assembly ----------

	def topo(self):
		order = []
		visiting = {}
		done = {}
		def visit(m):
			if m in done or m in visiting:
				return
			visiting[m] = True
			deps = list(m.refdeps.values()) + list(m.depmods.values())
			for d in deps:
				if d is not self.entry:
					visit(d)
			visiting.pop(m, None)
			done[m] = True
			order.append(m)
		for d in list(self.entry.refdeps.values()) + list(self.entry.depmods.values()):
			if d is not self.entry:
				visit(d)
		return order

	def bundle(self, entry):
		self.root = os.path.dirname(os.path.abspath(entry)) or "."
		m = Mod("", entry)
		m.rel = os.path.basename(entry)
		m.text = read_text(entry)
		m.lines = line_lengths(m.text)
		m.tokens = tokenize_text(m.text)
		m.tree = ast.parse(m.text)
		self.mods[""] = m
		self.entry = m
		self.analyze(m)
		for mm in self.mods.values():
			self.toplvl_deps(mm)
		order = self.topo()
		premerged = []
		for mm in [m] + order:
			for strip, ext in mm.imports_at.values():
				if strip:
					for line in ext:
						if line not in premerged:
							premerged.append(line)
		parts = []
		if premerged:
			parts.append("\n".join(merge_imports(premerged)))
		first_body = True
		for mm in order:
			body = self.rewrite(mm)
			if body.strip() == "":
				continue
			if first_body and premerged:
				body = body.lstrip("\n")
				first_body = False
			parts.append("############   from file: %s   ############\n\n%s" % (mm.rel, body.rstrip("\n")))
		entry_body = self.rewrite(m)
		if entry_body.strip() == "":
			entry_body = m.text
		if first_body and premerged:
			entry_body = entry_body.lstrip("\n")
		parts.append(entry_body.rstrip("\n"))
		if self.warnings:
			print("pybundle warnings:", file=sys.stderr)
			for w in self.warnings:
				print("  " + w, file=sys.stderr)
		return "\n\n".join(parts) + "\n"

def bundle(entry):
	return Bundler().bundle(entry)

def main():
	ap = argparse.ArgumentParser(description="Bundle a python project into a single file.")
	ap.add_argument("entry", help="entry script")
	ap.add_argument("-o", dest="out", help="write output to file")
	args = ap.parse_args()
	result = bundle(args.entry)
	if args.out:
		with open(args.out, "w") as f:
			f.write(result)
	else:
		sys.stdout.write(result)

if __name__ == "__main__":
	main()
