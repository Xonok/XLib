import argparse,fcntl,glob,hashlib,json,os,subprocess,sys,time
from contextlib import contextmanager

MAX_INSTANCES = 8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".agents")
LOCK = os.path.join(DIR, "lock")
IDS = os.path.join(DIR, "ids.json")
CLAIMS = os.path.join(DIR, "claims.json")
ROTATION_CURSOR = os.path.join(DIR, "rotation.json")
RULE_CURSOR = os.path.join(DIR, "rule-cursor.json")
SUBAGENT_CTX = os.path.join(DIR, "subagent-ctx.json")
CTX_BUDGET = 8
CTX_WARN_AT = 6
BATCH_FLUSH_N = 3
BATCH_FLUSH_AGE = 60

def rule_files(ws_root):
	paths = [os.path.join(ws_root, "AGENTS.md")]
	paths += sorted(glob.glob(os.path.join(ws_root, ".opencode", "agent", "*.md")))
	paths += sorted(glob.glob(os.path.join(ws_root, "style", "*.md")))
	return paths

def file_hash(path):
	try:
		with open(path, "rb") as f:
			return hashlib.sha256(f.read()).hexdigest()
	except OSError:
		return None

def load(path, default):
	try:
		with open(path) as f:
			return json.load(f)
	except (FileNotFoundError, ValueError):
		return default

def save(path, data):
	tmp = path + ".tmp"
	with open(tmp, "w") as f:
		json.dump(data, f, indent=2)
		f.write("\n")
	os.replace(tmp, path)

@contextmanager
def locked():
	os.makedirs(DIR, exist_ok=True)
	with open(LOCK, "w") as f:
		fcntl.flock(f, fcntl.LOCK_EX)
		try:
			yield
		finally:
			fcntl.flock(f, fcntl.LOCK_UN)

def opencode_pid():
	pid = os.getpid()
	while True:
		with open("/proc/%s/stat" % pid) as f:
			parts = f.read().split()
		comm = parts[1].strip("()")
		ppid = int(parts[3])
		if comm == "opencode":
			return pid
		if pid in (1, ppid):
			return None
		pid = ppid

def session_key():
	name = os.environ.get("OPENCODE_AGENT_ID")
	if name:
		return name
	pid = opencode_pid()
	return "pid-%s" % (pid or os.getpid())

def workspace_root():
	"""Workspace folder of this session: nearest ancestor of the opencode
	process's cwd that has a .agents dir, else this process's cwd ancestry,
	else ROOT."""
	start = ROOT
	pid = opencode_pid()
	if pid:
		try:
			start = os.path.realpath(os.readlink("/proc/%s/cwd" % pid))
		except OSError:
			pass
	for base in [start, os.getcwd()]:
		while True:
			if os.path.isdir(os.path.join(base, ".agents")):
				return base
			parent = os.path.dirname(base)
			if parent == base:
				break
			base = parent
	return ROOT

def ws_tag():
	return os.path.basename(os.path.abspath(workspace_root()))

def candidate_roots():
	roots = []
	for base in [ROOT, os.getcwd()]:
		while True:
			if base not in roots:
				roots.append(base)
			parent = os.path.dirname(base)
			if parent == base:
				break
			base = parent
	return roots

def root_for_tag(tag):
	for root in candidate_roots():
		if os.path.basename(root) == tag:
			return root
	return None

def agent_role():
	return os.environ.get("OPENCODE_AGENT_ROLE") or "unknown"

def qualify(agent):
	if "/" in agent:
		return agent
	return "%s/%s" % (ws_tag(), agent)

def allocate_instance(role, tag, ids):
	"""Return next available instance number for (tag, role), recycling dead processes."""
	prefix = tag + "/" + role + "-"
	taken = set()
	for v in ids.values():
		if v.startswith(prefix):
			try:
				n = int(v.rsplit("-", 1)[1])
				taken.add(n)
			except (ValueError, IndexError):
				pass
	# Also check for dead processes among taken numbers
	for n_val in list(taken):
		session_key_for_num = None
		for k, val in ids.items():
			if val == tag + "/" + role + "-" + str(n_val):
				session_key_for_num = k
				break
		if session_key_for_num and session_key_for_num.startswith("pid-"):
			try:
				pid = int(session_key_for_num.split("-")[1])
				if not is_process_alive(pid):
					taken.discard(n_val)
			except (ValueError, IndexError):
				pass
	for n in range(1, MAX_INSTANCES + 1):
		if n not in taken:
			return n
	return None

def migrate_ids():
	"""Upgrade old-format ids, claims, and cursors to new role-N format.
	Old slot-based IDs (workspace/a1) are simply dropped -- fresh start per plan."""
	tag = ws_tag()
	ids = load(IDS, {})
	changed = False
	# Remove old slot-based entries (workspace/a1, workspace/a2, etc.)
	old_slots = {k for k, v in ids.items() if "/" in v and v.split("/", 1)[1].startswith("a") and v.split("/", 1)[1][1:].isdigit()}
	for k in old_slots:
		del ids[k]
		changed = True
	if changed:
		save(IDS, ids)
	# Clean claims and cursors of old slot references
	claims = load(CLAIMS, {})
	cursors = load(RULE_CURSOR, {})
	changed_c = False
	changed_cu = False
	for k in list(claims.keys()):
		if k not in ids:
			claims.pop(k, None)
			changed_c = True
	for k in list(cursors.keys()):
		if k not in ids:
			cursors.pop(k, None)
			changed_cu = True
	if changed_c:
		save(CLAIMS, claims)
	if changed_cu:
		save(RULE_CURSOR, cursors)

def my_id():
	key = session_key()
	if not key.startswith("pid-"):
		return qualify(key)
	with locked():
		recycle_dead_slots()
		migrate_ids()
		ids = load(IDS, {})
		if key in ids:
			return qualify(ids[key])
		tag = ws_tag()
		role = agent_role()
		n = allocate_instance(role, tag, ids)
		if n is None:
			sys_stderr("no free instance for role %s in %s (limit %s); set OPENCODE_AGENT_ID to pick one" % (role, tag, MAX_INSTANCES))
			raise SystemExit(1)
		agent_id = "%s/%s-%d" % (tag, role, n)
		ids[key] = agent_id
		save(IDS, ids)
		return agent_id

def sys_stderr(msg):
	print(msg, file=sys.stderr)

def is_process_alive(pid):
	"""Check if a process with the given PID is still running."""
	return os.path.exists("/proc/%s" % pid)

def recycle_dead_slots():
	"""Remove ids.json entries for processes that no longer exist, freeing their instance numbers."""
	ids = load(IDS, {})
	claims = load(CLAIMS, {})
	cursors = load(RULE_CURSOR, {})
	dead_keys = []
	for key in ids:
		if key.startswith("pid-"):
			try:
				pid = int(key.split("-")[1])
				if not is_process_alive(pid):
					dead_keys.append(key)
			except (ValueError, IndexError):
				pass
	for key in dead_keys:
		agent_id = ids[key]
		ids.pop(key, None)
		claims.pop(agent_id, None)
		cursors.pop(agent_id, None)
	if dead_keys:
		save(IDS, ids)
		save(CLAIMS, claims)
		save(RULE_CURSOR, cursors)

def instance_note_path(agent_id):
	"""Return the instance note path for an agent ID like 'XLib/planner-1'."""
	tag_role_num = agent_id.split("/")[-1]
	parts = tag_role_num.rsplit("-", 1)
	if len(parts) != 2:
		return os.path.join(DIR, "agent-notes-%s.md" % tag_role_num)
	role, num = parts
	# Find workspace root for this agent's tag
	tag = agent_id.split("/")[0] if "/" in agent_id else ws_tag()
	root = root_for_tag(tag) or workspace_root()
	return os.path.join(root, ".agents", "agent-notes-%s-%s.md" % (role, num))

def role_note_path(role, ws_root=None):
	"""Return the role notes path for a role within a workspace."""
	if ws_root is None:
		ws_root = workspace_root()
	return os.path.join(ws_root, ".agents", "role-notes-%s.md" % role)

def claim_paths(paths):
	return [os.path.abspath(p) for p in paths]

def cmd_id(args):
	print(my_id())

def cmd_workspace(args):
	root = workspace_root()
	print("%s (%s)" % (root, ws_tag()))

def cmd_instance_note(args):
	print(instance_note_path(my_id()))

def cmd_note(args):
	"""Deprecated alias for instance-note."""
	print(instance_note_path(my_id()))

def cmd_role_note(args):
	role = args.role if args.role else agent_role()
	ws_root = workspace_root()
	if args.workspace:
		tag_root = root_for_tag(args.workspace)
		if tag_root:
			ws_root = tag_root
		else:
			sys_stderr("unknown workspace tag: %s" % args.workspace)
			raise SystemExit(1)
	print(role_note_path(role, ws_root))

def cmd_claim(args):
	paths = claim_paths(args.paths)
	agent = my_id()
	with locked():
		claims = load(CLAIMS, {})
		owner = {}
		for slot, owned in claims.items():
			for p in owned:
				owner[p] = slot
		conflicts = [p for p in paths if p in owner and owner[p] != agent]
		if conflicts and not args.force:
			for p in conflicts:
				sys_stderr("%s is held by %s" % (p, owner[p]))
			sys_stderr("pass --force to steal it (the holder may be editing)")
			raise SystemExit(1)
		for slot, owned in claims.items():
			claims[slot] = [p for p in owned if p not in conflicts]
		mine = claims.get(agent, [])
		for p in paths:
			if p not in mine:
				mine.append(p)
		claims[agent] = mine
		save(CLAIMS, claims)
	for p in paths:
		print("claimed %s" % p)

def cmd_release(args):
	paths = claim_paths(args.paths)
	agent = my_id()
	with locked():
		claims = load(CLAIMS, {})
		mine = [p for p in claims.get(agent, []) if p not in paths]
		claims[agent] = mine
		save(CLAIMS, claims)
	for p in paths:
		print("released %s" % p)

def cmd_release_all(args):
	agent = my_id()
	with locked():
		claims = load(CLAIMS, {})
		claims.pop(agent, None)
		save(CLAIMS, claims)
	print("released all")

def cmd_status(args):
	with locked():
		claims = load(CLAIMS, {})
		if not claims:
			print("no claims")
			return
		for slot, owned in sorted(claims.items()):
			if owned:
				print("%s: %s" % (slot, ", ".join(owned)))

def cmd_role_status(args):
	"""Show role note claims (claims on role-notes-{role}.md files)."""
	with locked():
		claims = load(CLAIMS, {})
		if not claims:
			print("no claims")
			return
		for slot, owned in sorted(claims.items()):
			role_claims = [p for p in owned if os.path.basename(p).startswith("role-notes-")]
			if role_claims:
				print("%s: %s" % (slot, ", ".join(role_claims)))

def cmd_role_claim(args):
	"""Claim role notes for the caller's role (or explicit role)."""
	role = args.role if args.role else agent_role()
	ws_root = workspace_root()
	if args.workspace:
		tag_root = root_for_tag(args.workspace)
		if tag_root:
			ws_root = tag_root
		else:
			sys_stderr("unknown workspace tag: %s" % args.workspace)
			raise SystemExit(1)
	path = os.path.abspath(role_note_path(role, ws_root))
	agent = my_id()
	with locked():
		claims = load(CLAIMS, {})
		owner = {}
		for slot, owned in claims.items():
			for p in owned:
				owner[p] = slot
		if path in owner and owner[path] != agent:
			if not args.force:
				sys_stderr("%s is held by %s" % (path, owner[path]))
				sys_stderr("pass --force to steal it (the holder may be editing)")
				raise SystemExit(1)
			for slot, owned in claims.items():
				claims[slot] = [p for p in owned if p != path]
		mine = claims.get(agent, [])
		if path not in mine:
			mine.append(path)
		claims[agent] = mine
		save(CLAIMS, claims)
	print("claimed %s" % path)

def cmd_role_release(args):
	"""Release role notes for the caller's role (or explicit role)."""
	role = args.role if args.role else agent_role()
	ws_root = workspace_root()
	if args.workspace:
		tag_root = root_for_tag(args.workspace)
		if tag_root:
			ws_root = tag_root
		else:
			sys_stderr("unknown workspace tag: %s" % args.workspace)
			raise SystemExit(1)
	path = os.path.abspath(role_note_path(role, ws_root))
	agent = my_id()
	with locked():
		claims = load(CLAIMS, {})
		mine = [p for p in claims.get(agent, []) if p != path]
		claims[agent] = mine
		save(CLAIMS, claims)
	print("released %s" % path)

WORKER_MAP = {
	"coding": "worker-mimo",
	"reasoning": "worker-nemotron-ultra",
	"bulk": "worker-nemotron-lightning",
	"general": "worker-ling",
}

def cmd_dispatch(args):
	cat = args.category.lower()
	if cat not in WORKER_MAP:
		sys_stderr("unknown category: %s (valid: %s)" % (cat, ", ".join(WORKER_MAP)))
		raise SystemExit(2)
	print(WORKER_MAP[cat])

def resolve_type(name):
	name = name.lower()
	return WORKER_MAP.get(name, name)

def ctx_data():
	return load(SUBAGENT_CTX, {})

def ctx_save(data):
	save(SUBAGENT_CTX, data)

def ctx_ws(data):
	return data.setdefault(ws_tag(), {"registry": {}, "queues": {}})

def cmd_ctx_status(args):
	now = time.time()
	with locked():
		data = ctx_data()
		ws = ctx_ws(data)
		reg = ws.get("registry", {})
		queues = ws.get("queues", {})
		if args.type:
			t = resolve_type(args.type)
			entry = reg.get(t)
			q = queues.get(t, [])
			if not entry and not q:
				print("no context for %s" % t)
				return
			if entry:
				n = entry["dispatches"]
				suffix = ""
				if n >= CTX_BUDGET:
					suffix = " | ROTATE NOW"
				elif n >= CTX_WARN_AT:
					suffix = " | rotate soon"
				print("%s: %s (%d/%d dispatches)%s" % (t, entry["task_id"], n, CTX_BUDGET, suffix))
			if q:
				age = int(now - q[0]["ts"])
				n = len(q)
				flush = ""
				if n >= BATCH_FLUSH_N or age >= BATCH_FLUSH_AGE:
					flush = " | FLUSH READY"
				print("queue %s: %d pending (oldest %ds)%s" % (t, n, age, flush))
			return
		shown = set()
		for t in sorted(reg):
			entry = reg[t]
			n = entry["dispatches"]
			suffix = ""
			if n >= CTX_BUDGET:
				suffix = " | ROTATE NOW"
			elif n >= CTX_WARN_AT:
				suffix = " | rotate soon"
			print("%s: %s (%d/%d dispatches)%s" % (t, entry["task_id"], n, CTX_BUDGET, suffix))
			shown.add(t)
		for t in sorted(queues):
			q = queues[t]
			if not q:
				continue
			age = int(now - q[0]["ts"])
			n = len(q)
			flush = ""
			if n >= BATCH_FLUSH_N or age >= BATCH_FLUSH_AGE:
				flush = " | FLUSH READY"
			print("queue %s: %d pending (oldest %ds)%s" % (t, n, age, flush))
			shown.add(t)
		if not shown:
			print("no subagent context")

def cmd_ctx_set(args):
	t = resolve_type(args.type)
	now = time.time()
	with locked():
		data = ctx_data()
		ws = ctx_ws(data)
		reg = ws.setdefault("registry", {})
		for other, entry in reg.items():
			if other != t and entry.get("task_id") == args.task_id:
				sys_stderr("warning: task_id %s already registered to %s" % (args.task_id, other))
		reg[t] = {"task_id": args.task_id, "dispatches": 0, "ts": now}
		ctx_save(data)
	print("%s -> %s" % (t, args.task_id))

def cmd_ctx_get(args):
	t = resolve_type(args.type)
	with locked():
		data = ctx_data()
		entry = ctx_ws(data).get("registry", {}).get(t)
		if entry:
			print(entry["task_id"])

def cmd_ctx_bump(args):
	t = resolve_type(args.type)
	with locked():
		data = ctx_data()
		entry = ctx_ws(data).get("registry", {}).get(t)
		if not entry:
			sys_stderr("no active task_id for %s" % t)
			raise SystemExit(1)
		entry["dispatches"] += 1
		entry["ts"] = time.time()
		ctx_save(data)
		print(entry["dispatches"])

def cmd_ctx_rotate(args):
	t = resolve_type(args.type)
	with locked():
		data = ctx_data()
		entry = ctx_ws(data).get("registry", {}).pop(t, None)
		ctx_save(data)
	if entry:
		print("dropped %s task_id" % t)
	else:
		print("no task_id for %s" % t)

def cmd_ctx_queue(args):
	t = resolve_type(args.type)
	now = time.time()
	with locked():
		data = ctx_data()
		ws = ctx_ws(data)
		q = ws.setdefault("queues", {}).setdefault(t, [])
		for text in args.text:
			q.append({"text": text, "ts": now})
		total = len(q)
		ctx_save(data)
	print("queued %d task(s) for %s (%d pending)" % (len(args.text), t, total))

def cmd_ctx_batch(args):
	t = resolve_type(args.type)
	now = time.time()
	with locked():
		data = ctx_data()
		q = ctx_ws(data).get("queues", {}).get(t, [])
		if not q:
			print("no pending batch for %s" % t)
			return
		for item in q:
			age = int(now - item["ts"])
			print("[%ds] %s" % (age, item["text"]))

def cmd_ctx_flush(args):
	t = resolve_type(args.type)
	now = time.time()
	with locked():
		data = ctx_data()
		ws = ctx_ws(data)
		q = ws.get("queues", {}).get(t, [])
		if not q:
			print("no pending batch for %s" % t)
			return
		for item in q:
			age = int(now - item["ts"])
			print("[%ds] %s" % (age, item["text"]))
		n = len(q)
		ws.get("queues", {})[t] = []
		ctx_save(data)
	sys_stderr("flushed %d task(s) for %s" % (n, t))

def cmd_ctx_reset(args):
	with locked():
		data = ctx_data()
		if args.type:
			t = resolve_type(args.type)
			ws = ctx_ws(data)
			ws.get("registry", {}).pop(t, None)
			ws.get("queues", {}).pop(t, None)
			ctx_save(data)
			print("reset %s" % t)
		else:
			tag = ws_tag()
			data.pop(tag, None)
			ctx_save(data)
			print("reset all context for %s" % tag)

def cmd_ctx(args):
	{"status": cmd_ctx_status, "set": cmd_ctx_set, "get": cmd_ctx_get,
	 "bump": cmd_ctx_bump, "rotate": cmd_ctx_rotate, "queue": cmd_ctx_queue,
	 "batch": cmd_ctx_batch, "flush": cmd_ctx_flush, "reset": cmd_ctx_reset}[args.ctx_cmd](args)

def cmd_news(args):
	agent = my_id()
	with locked():
		seen = load(RULE_CURSOR, {}).get(agent, {})
		files = [p for p in rule_files(workspace_root()) if file_hash(p) is not None]
		changed = [p for p in files if file_hash(p) != seen.get(p)]
		if args.status:
			print("not caught up" if changed else "caught up")
		else:
			if args.peek:
				if changed:
					print("changed since last looked:\n" + "\n".join(changed))
				else:
					print("no new guideline changes")
			else:
				cursors = load(RULE_CURSOR, {})
				cursors[agent] = {p: file_hash(p) for p in files}
				save(RULE_CURSOR, cursors)
				if changed:
					print("new guideline changes (now seen):\n" + "\n".join(changed))
				else:
					print("no new guideline changes")

def git_status(repo):
	"""Return a list of dirty path strings for a git repo (read-only)."""
	try:
		out = subprocess.check_output(["git", "-C", repo, "status", "--porcelain", "-z"],
			stderr=subprocess.DEVNULL).decode("utf-8", "replace")
	except (subprocess.CalledProcessError, OSError):
		return None
	dirty = []
	i = 0
	parts = out.split("\0")
	while i < len(parts):
		entry = parts[i]
		if not entry:
			break
		head = entry[:2]
		path = entry[3:]
		if head.startswith("R"):
			i += 1
			dirty.append(path)
			if i < len(parts):
				dirty.append(parts[i])
		else:
			dirty.append(path)
		i += 1
	return dirty

def under(base, path):
	"""True if path is base or is inside base (prefix at a component boundary)."""
	if base in (".", ""):
		return True
	if base == path:
		return True
	return path.startswith(base.rstrip("/") + "/")

def nearest_git(path):
	base = os.path.dirname(os.path.abspath(path))
	while True:
		if os.path.isdir(os.path.join(base, ".git")):
			return base
		parent = os.path.dirname(base)
		if parent == base:
			return None
		base = parent

def cmd_check_clean(args):
	abspaths = [os.path.abspath(p) for p in args.paths]
	if args.repo:
		repos = {os.path.realpath(args.repo): abspaths}
	else:
		repos = {}
		for p in abspaths:
			repos.setdefault(nearest_git(p) or p, []).append(p)
	blocked_all = []
	if len(repos) > 1:
		sys_stderr("paths span multiple repos: %s" % ", ".join(sorted(repos)))
		raise SystemExit(2)
	for repo, paths in repos.items():
		dirty = git_status(repo)
		if dirty is None:
			sys_stderr("%s is not a git repo (pass --repo)" % repo)
			raise SystemExit(2)
		want = [os.path.relpath(p, repo) for p in paths]
		blocked_all += sorted({d for d in dirty if any(under(w, d) for w in want)})
	if not blocked_all:
		print("clean")
		return
	for d in blocked_all:
		print("dirty %s" % d)
	raise SystemExit(1)

def main():
	parser = argparse.ArgumentParser(prog="agent-coord")
	sub = parser.add_subparsers(dest="command", required=True)
	sub.add_parser("id", help="print this agent's workspace-qualified id")
	sub.add_parser("note", help="(deprecated) print this agent's instance notes file path")
	sub.add_parser("instance-note", help="print this agent's instance notes file path")
	sub.add_parser("workspace", help="print this session's workspace root and tag")
	p = sub.add_parser("claim", help="claim files before editing")
	p.add_argument("paths", nargs="+")
	p.add_argument("--force", action="store_true", help="steal files held by the other agent")
	p = sub.add_parser("release", help="release claimed files")
	p.add_argument("paths", nargs="+")
	sub.add_parser("release-all", help="release everything this agent claimed")
	sub.add_parser("status", help="show who holds what")
	p = sub.add_parser("news", help="report rule-file changes since this agent last looked (and mark them seen)")
	p.add_argument("--peek", action="store_true", help="report changes without marking them seen")
	p.add_argument("--status", action="store_true", help="print caught-up status without changing anything")
	p = sub.add_parser("check-clean", help="report which of the given paths have uncommitted changes")
	p.add_argument("paths", nargs="+", help="files or dirs under the repo to check")
	p.add_argument("--repo", default=None, help="git working tree (default: inferred from the given paths)")
	p = sub.add_parser("dispatch", help="get the worker model for a task category")
	p.add_argument("category", choices=["coding", "reasoning", "bulk", "general"], help="task category")
	# Role-based note commands
	p = sub.add_parser("role-note", help="print role notes file path")
	p.add_argument("--role", default=None, help="role (default: caller's role)")
	p.add_argument("--workspace", default=None, help="workspace tag (default: caller's workspace)")
	p = sub.add_parser("role-claim", help="claim role notes for this role")
	p.add_argument("--role", default=None, help="role (default: caller's role)")
	p.add_argument("--workspace", default=None, help="workspace tag (default: caller's workspace)")
	p.add_argument("--force", action="store_true", help="steal role notes held by another agent")
	p = sub.add_parser("role-release", help="release role notes for this role")
	p.add_argument("--role", default=None, help="role (default: caller's role)")
	p.add_argument("--workspace", default=None, help="workspace tag (default: caller's workspace)")
	sub.add_parser("role-status", help="show role note claims")
	p = sub.add_parser("ctx", help="manage subagent context (task_ids, batch queues)")
	cp = p.add_subparsers(dest="ctx_cmd", required=True)
	sp = cp.add_parser("status", help="show subagent context status")
	sp.add_argument("--type", default=None, help="filter to a specific subagent type")
	sp = cp.add_parser("set", help="register or replace a task_id for a subagent type")
	sp.add_argument("type", help="subagent type or category name")
	sp.add_argument("task_id", help="task_id to register")
	sp = cp.add_parser("get", help="print the active task_id for a type (or nothing)")
	sp.add_argument("type", help="subagent type or category name")
	sp = cp.add_parser("bump", help="increment dispatch count for a type")
	sp.add_argument("type", help="subagent type or category name")
	sp = cp.add_parser("rotate", help="drop the registry entry for a type")
	sp.add_argument("type", help="subagent type or category name")
	sp = cp.add_parser("queue", help="add tasks to a type's batch queue")
	sp.add_argument("type", help="subagent type or category name")
	sp.add_argument("text", nargs="+", help="task description(s) to queue")
	sp = cp.add_parser("batch", help="show queued tasks for a type")
	sp.add_argument("type", help="subagent type or category name")
	sp = cp.add_parser("flush", help="print and clear queued tasks for a type")
	sp.add_argument("type", help="subagent type or category name")
	sp = cp.add_parser("reset", help="clear context state")
	sp.add_argument("--type", default=None, help="reset only this type (else reset all)")
	args = parser.parse_args()
	{"id": cmd_id, "note": cmd_note, "instance-note": cmd_instance_note,
	 "workspace": cmd_workspace, "claim": cmd_claim,
	 "release": cmd_release, "release-all": cmd_release_all, "status": cmd_status,
	 "news": cmd_news, "check-clean": cmd_check_clean, "dispatch": cmd_dispatch,
	 "role-note": cmd_role_note, "role-claim": cmd_role_claim,
	 "role-release": cmd_role_release, "role-status": cmd_role_status,
	 "ctx": cmd_ctx}[args.command](args)

if __name__ == "__main__":
	main()
