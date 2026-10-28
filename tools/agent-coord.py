import argparse,fcntl,glob,hashlib,json,os,subprocess,sys,time
from contextlib import contextmanager

MAX_INSTANCES = 8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".agents")
LOCK = os.path.join(DIR, "lock")
IDS = os.path.join(DIR, "ids.json")
CLAIMS = os.path.join(DIR, "claims.json")
RULE_CURSOR = os.path.join(DIR, "rule-cursor.json")
SUBAGENT_CTX = os.path.join(DIR, "subagent-ctx.json")
CTX_BUDGET = 8
CTX_WARN_AT = 6
BATCH_FLUSH_N = 3
BATCH_FLUSH_AGE = 60

def rule_files(ws_root):
	"""The rule files of a workspace.

	XLib keeps its style rules in `doc/style/`, and the pointer table in `AGENTS.md`
	names that folder, so a glob of `style/` alone finds nothing: the announcement
	that carries the rules out to other agents had no rules to announce.
	"""
	paths = [os.path.join(ws_root, "AGENTS.md")]
	paths += sorted(glob.glob(os.path.join(ws_root, ".opencode", "agent", "*.md")))
	paths += sorted(glob.glob(os.path.join(ws_root, "doc", "style", "*.md")))
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

# Personal files functions

def resolve_person_id(args_person):
	"""Resolve person id with precedence: --person, git config, $USER, else error."""
	if args_person:
		return args_person
	try:
		name = subprocess.check_output(
			["git", "-C", workspace_root(), "config", "user.name"],
			stderr=subprocess.DEVNULL, text=True).strip()
		if name:
			return name
	except (subprocess.CalledProcessError, FileNotFoundError):
		pass
	name = os.environ.get("USER")
	if name:
		return name
	sys_stderr("no person id found; set --person or configure git config user.name")
	raise SystemExit(1)

def sanitize_person_id(pid):
	"""Sanitize person id for path safety: keep [A-Za-z0-9._-], replace other chars with -, strip leading/trailing .- and collapse multiple -."""
	import re
	pid = re.sub(r"[^A-Za-z0-9._-]", "-", pid)
	pid = pid.strip("-._")
	pid = re.sub(r"-+", "-", pid)
	return pid

def cmd_personal_whoami(args):
	person = resolve_person_id(args.person)
	pid = sanitize_person_id(person)
	if not pid:
		sys_stderr("person id resolved to empty after sanitization")
		raise SystemExit(1)
	print(pid)

def cmd_personal_path(args):
	person = resolve_person_id(args.person)
	pid = sanitize_person_id(person)
	base = os.path.join("personal", pid)
	if args.file:
		print(os.path.join(base, args.file))
	else:
		print(base)

def _append_gitignore(ws_root, fn):
	"""Append /<fn> to .gitignore if not already present."""
	gitignore_path = os.path.join(ws_root, ".gitignore")
	line = "/%s" % fn
	try:
		with open(gitignore_path, "r") as f:
			existing = f.read()
	except OSError:
		existing = ""
	if line not in existing.splitlines():
		with open(gitignore_path, "a") as f:
			if existing and not existing.endswith("\n"):
				f.write("\n")
			f.write(line + "\n")

def cmd_personal_init(args):
	person = resolve_person_id(args.person)
	pid = sanitize_person_id(person)
	if not pid:
		sys_stderr("person id resolved to empty after sanitization")
		raise SystemExit(1)
	files = args.files.split(" ") if isinstance(args.files, str) else args.files
	ws_root = os.path.abspath(args.root) if args.root else workspace_root()
	if not os.path.isdir(ws_root):
		sys_stderr("--root is not a directory: %s" % ws_root)
		raise SystemExit(1)
	person_dir = os.path.join("personal", pid)
	for fname in files:
		fn = fname.strip(" ")
		if not fn:
			continue
		person_path = os.path.join(person_dir, fn)
		abs_person_path = os.path.join(ws_root, person_path)
		root_path = os.path.join(ws_root, fn)
		# 1. If personal file exists → skip silently, ensure symlink
		if os.path.isfile(abs_person_path):
			if os.path.islink(root_path):
				if os.readlink(root_path) == person_path:
					print("%s ready (existing)" % person_path)
					continue
				sys_stderr("%s exists as symlink to wrong target; refusing to overwrite" % root_path)
				raise SystemExit(1)
			if os.path.exists(root_path):
				sys_stderr("%s exists as real file/directory; refusing to symlink over it (file was not migrated)" % root_path)
				raise SystemExit(1)
			os.symlink(person_path, root_path)
			_append_gitignore(ws_root, fn)
			print("%s ready (existing, symlinked)" % person_path)
			continue
		# 2. Root exists as real file and --seed current → migrate
		if args.seed == "current" and os.path.isfile(root_path) and not os.path.islink(root_path):
			os.makedirs(os.path.dirname(abs_person_path), exist_ok=True)
			try:
				subprocess.run(["git", "-C", ws_root, "ls-files", "--error-unmatch", fn],
					check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				# Tracked → git mv (preserves history via rename detection)
				subprocess.run(["git", "-C", ws_root, "mv", fn, person_path],
					check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			except subprocess.CalledProcessError:
				# Not tracked → plain rename + git add
				os.rename(root_path, abs_person_path)
				subprocess.run(["git", "-C", ws_root, "add", person_path], check=True)
			# Create symlink
			os.symlink(person_path, root_path)
			_append_gitignore(ws_root, fn)
			print("%s ready (migrated)" % person_path)
			continue
		# 3. Template path
		os.makedirs(os.path.dirname(abs_person_path), exist_ok=True)
		subject = os.path.basename(ws_root)
		basename = os.path.splitext(fn)[0]
		with open(abs_person_path, "w") as f:
			f.write("# %s %s — %s\n" % (subject, basename, pid))
			f.write("\n")
			f.write("(empty template — edit me. To absorb an existing root file: personal init --seed current)\n")
		# Create symlink
		if os.path.islink(root_path):
			if os.readlink(root_path) != person_path:
				sys_stderr("%s symlink points to wrong target; refusing to overwrite" % root_path)
				raise SystemExit(1)
		elif os.path.exists(root_path):
			sys_stderr("%s exists as real file/directory; refusing to symlink over it" % root_path)
			raise SystemExit(1)
		else:
			os.symlink(person_path, root_path)
		_append_gitignore(ws_root, fn)
		print("%s ready (template)" % person_path)

def cmd_personal(args):
	{"whoami": cmd_personal_whoami, "path": cmd_personal_path,
	 "init": cmd_personal_init}[args.personal_cmd](args)

@contextmanager
def locked():
	os.makedirs(DIR, exist_ok=True)
	with open(LOCK, "w") as f:
		fcntl.flock(f, fcntl.LOCK_EX)
		try:
			yield
		finally:
			fcntl.flock(f, fcntl.LOCK_UN)

def proc_argv(pid):
	"""The argument vector of a process, as a list of strings."""
	try:
		with open("/proc/%s/cmdline" % pid, "rb") as f:
			return f.read().decode("utf-8", "replace").split("\0")
	except OSError:
		return []

def proc_cwd(pid):
	"""The working directory of a process, or None if it cannot be read."""
	try:
		return os.path.realpath(os.readlink("/proc/%s/cwd" % pid))
	except OSError:
		return None

def proc_starttime(pid):
	"""The start time of a process, in clock ticks since boot."""
	try:
		with open("/proc/%s/stat" % pid) as f:
			parts = f.read().split()
		return int(parts[21])
	except (OSError, IndexError, ValueError):
		return 0

def is_service(argv):
	"""True for the opencode background service.

	One service runs for the whole machine and every session's tool shell is its
	child, so the service is not evidence about the session that is asking: it is
	the same process for every session, and it works out of the home directory.
	"""
	return argv[1:2] == ["serve"]

def pick_opencode_pid(entries):
	"""Choose the opencode client among ancestor processes, nearest first.

	`entries` is a list of (pid, comm, argv). The service is skipped rather
	than used as a fallback: it is the same process for every session on the
	machine, it works out of the home directory, and it gives every session one
	identity. So the walk settles on the client, and the service is not an
	answer.
	"""
	for pid, comm, argv in entries:
		if comm != "opencode":
			continue
		if is_service(argv):
			continue
		return pid
	return None

def opencode_ancestors():
	"""The opencode processes in this process's ancestry, nearest first.

	Each entry is (pid, comm, argv).
	"""
	entries = []
	pid = os.getpid()
	while True:
		try:
			with open("/proc/%s/stat" % pid) as f:
				parts = f.read().split()
		except OSError:
			break
		comm = parts[1].strip("()")
		ppid = int(parts[3])
		if comm == "opencode":
			entries.append((pid, comm, proc_argv(pid)))
		if pid in (1, ppid):
			break
		pid = ppid
	return entries

def opencode_pid():
	"""The pid of the opencode client in this process's ancestry, or None."""
	return pick_opencode_pid(opencode_ancestors())

def opencode_service_pid():
	"""The pid of the opencode background service in this process's ancestry."""
	for pid, comm, argv in opencode_ancestors():
		if comm == "opencode" and is_service(argv):
			return pid
	return None

def opencode_clients():
	"""The opencode clients on the machine: (pid, argv, cwd) for each.

	The service is left out. Under opencode 2 the tool shell descends from the
	service rather than from the client, so the client is not an ancestor and has
	to be found by what it says about itself: it names the session it serves, and
	it works in the directory the session works in.
	"""
	clients = []
	for name in os.listdir("/proc"):
		if not name.isdigit():
			continue
		pid = int(name)
		try:
			with open("/proc/%s/comm" % pid) as f:
				comm = f.read().strip()
		except OSError:
			continue
		if comm != "opencode":
			continue
		argv = proc_argv(pid)
		if is_service(argv):
			continue
		clients.append((pid, argv, proc_cwd(pid)))
	return clients

def pick_session_client(clients, session_id, cwd, known):
	"""Choose the opencode client that owns this session.

	`clients` is a list of (pid, argv, cwd). `session_id` is the id the session
	knows itself by, `cwd` the directory this process runs in, and `known` the
	session keys this tool already holds an identity for.

	Three ways to name the owner, in order of how well they say it:
	  - the session id in the client's own arguments, which is exact;
	  - the only client working in the directory this session runs in;
	  - among several clients in that directory, the one this tool already
	    knows, so a `/new` in the same window keeps the same identity.
	"""
	clients = [c for c in clients if not is_service(c[1])]
	if session_id:
		for pid, argv, client_cwd in clients:
			if session_id in argv:
				return pid
	same = [c for c in clients if c[2] == cwd]
	if len(same) == 1:
		return same[0][0]
	if same:
		known_same = [c for c in same if "pid-%d" % c[0] in known]
		if len(known_same) == 1:
			return known_same[0][0]
		return max(same, key=lambda c: proc_starttime(c[0]))[0]
	return None

def session_client_pid():
	"""The pid of the opencode client that owns this session, or None.

	The client is found by what it says about itself: the session id in its own
	arguments, or the directory it works in. The service is never an answer.
	"""
	pid = opencode_pid()
	if pid:
		return pid
	clients = opencode_clients()
	if not clients:
		return None
	known = set(load(IDS, {}).keys())
	cwd = os.path.realpath(os.getcwd())
	return pick_session_client(clients, os.environ.get("OPENCODE_SESSION_ID"), cwd, known)

def session_key():
	"""The key that stands for this session in `ids.json`.

	Unless `OPENCODE_AGENT_ID` names one, it is the client's pid: two windows are
	two sessions, and one window keeps one identity across a `/new`, because the
	instance is the window and the notes file belongs to it. The session id is
	the second answer and the service's pid the last: the service is one process
	for the whole machine, so a key taken from it is shared by every session
	attached to it.
	"""
	name = os.environ.get("OPENCODE_AGENT_ID")
	if name:
		return name
	pid = session_client_pid()
	if pid:
		return "pid-%s" % pid
	session_id = os.environ.get("OPENCODE_SESSION_ID")
	if session_id:
		return "ses-%s" % session_id
	service = opencode_service_pid()
	return "pid-%s" % (service or os.getpid())

def workspace_root():
	"""Workspace folder of this session.

	The session's directory is the directory the opencode client that owns the
	session works in, and the tool shell runs in it as well. The service is not
	asked: one service runs for the whole machine and works out of the home
	directory, so a session attached to it would resolve every workspace to the
	home directory and find no rules there.
	"""
	bases = []
	client = session_client_pid()
	if client:
		cwd = proc_cwd(client)
		if cwd:
			bases.append(cwd)
	bases.append(os.path.realpath(os.getcwd()))
	for base in bases:
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
	ids = load(IDS, {})
	changed = False
	# Remove old slot-based entries (workspace/a1, workspace/a2, etc.)
	old_slots = {k for k, v in ids.items() if "/" in v and v.split("/", 1)[1].startswith("a") and v.split("/", 1)[1][1:].isdigit()}
	dropped = {ids[k] for k in old_slots}
	for k in old_slots:
		del ids[k]
		changed = True
	if changed:
		save(IDS, ids)
	# Clean claims and cursors of the old slot references, and of nothing else.
	# A claim is owned by an agent id while `ids.json` is keyed by session key, so
	# the two key spaces never meet: dropping every claim whose owner is not a
	# session key dropped every claim there was. `news` runs at session start, so
	# that is where the claims of the whole machine went.
	claims = load(CLAIMS, {})
	cursors = load(RULE_CURSOR, {})
	changed_c = False
	changed_cu = False
	for k in list(claims.keys()):
		if k in dropped:
			claims.pop(k, None)
			changed_c = True
	for k in list(cursors.keys()):
		if k in dropped:
			cursors.pop(k, None)
			changed_cu = True
	if changed_c:
		save(CLAIMS, claims)
	if changed_cu:
		save(RULE_CURSOR, cursors)

def service_keyed_ids(ids):
	"""The ids.json entries whose key names a live opencode service.

	One service runs for the whole machine, so an identity keyed by it was never
	a session's own: every session attached to the service was given that one
	id, that one notes file, that one rule cursor and that one set of claims.
	The key is the client's pid now, so these are leftovers of the sharing
	rather than the identity of anything.
	"""
	leftovers = {}
	for key, value in ids.items():
		if not key.startswith("pid-"):
			continue
		try:
			pid = int(key.split("-")[1])
		except ValueError:
			continue
		if is_service(proc_argv(pid)):
			leftovers[key] = value
	return leftovers

def absorb_leftover(ids, key, role):
	"""Take over a machine-wide leftover identity, and its claims, once.

	The service's pid used to be the session key, so every session attached to
	the service shared one identity, one notes file, one rule cursor and one set
	of claims. The key is the client's pid now, so the identity moves with the
	session that was using it and the claims and the cursor come with it, rather
	than being stranded where the guard would refuse the rightful owner.

	The id is re-tagged to the workspace the session is really in: the old tag
	was the home directory's name, which was never a workspace. Where this
	session already has an id, the leftover's claims merge into it and the
	leftover goes: a leftover is taken over once, so two sessions cannot end up
	sharing one identity.
	"""
	candidates = {}
	for old_key, old_id in service_keyed_ids(ids).items():
		suffix = old_id.split("/", 1)[1] if "/" in old_id else old_id
		if suffix.startswith(role + "-"):
			candidates[old_key] = (old_id, suffix)
	if len(candidates) != 1:
		return None
	old_key, (old_id, suffix) = next(iter(candidates.items()))
	new_id = ids.get(key) or "%s/%s" % (ws_tag(), suffix)
	ids[key] = new_id
	del ids[old_key]
	save(IDS, ids)
	claims = load(CLAIMS, {})
	if old_id in claims:
		merged = list(claims.get(new_id, []))
		for path in claims[old_id]:
			if path not in merged:
				merged.append(path)
		claims[new_id] = merged
		claims.pop(old_id, None)
		save(CLAIMS, claims)
	cursors = load(RULE_CURSOR, {})
	if old_id in cursors:
		cursors[new_id] = cursors.pop(old_id)
		save(RULE_CURSOR, cursors)
	return new_id

def retag_if_moved(ids, key, agent_id):
	"""Re-tag an identity that names another workspace.

	A session key is a process's pid, and a pid can be recycled: the session
	that had it dies, and a later session in another workspace is given the
	same pid. The identity it inherits names the *old* session's workspace,
	which sends its notes to another repository and leaves its claims under a
	name the session cannot see. The tag is the workspace, so the identity is
	re-tagged to the workspace the session is actually in.
	"""
	tag = ws_tag()
	if "/" not in agent_id:
		return agent_id
	old_tag, suffix = agent_id.split("/", 1)
	if old_tag == tag:
		return agent_id
	new_id = "%s/%s" % (tag, suffix)
	ids[key] = new_id
	save(IDS, ids)
	# The old session is gone: its pid belongs to a different process now, so
	# the dead-pid reaper will never collect it. Its claims are stale, and
	# moving them to this session would have this session holding files it
	# never touched, blocking whoever comes next. They are dropped.
	claims = load(CLAIMS, {})
	if agent_id in claims:
		claims.pop(agent_id, None)
		save(CLAIMS, claims)
	cursors = load(RULE_CURSOR, {})
	if agent_id in cursors:
		cursors.pop(agent_id, None)
		save(RULE_CURSOR, cursors)
	return new_id

def my_id():
	key = session_key()
	if not key.startswith("pid-"):
		return qualify(key)
	with locked():
		recycle_dead_slots()
		migrate_ids()
		ids = load(IDS, {})
		absorbed = absorb_leftover(ids, key, agent_role())
		if absorbed:
			return qualify(absorbed)
		if key in ids:
			return qualify(retag_if_moved(ids, key, ids[key]))
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
	"coding": "worker-north-mini-code",
	"reasoning": "worker-nemotron-ultra",
	"bulk": "worker-nemotron-lightning",
	# 2026-10-22: the previous target, worker-longcat, was WITHDRAWN —
	# longcat-2.5-preview-free is no longer in the Zen catalogue and opencode answers
	# `provider.no-route: Model unavailable` — and the fallback it named,
	# worker-ling, is withdrawn too. A dispatch to a dead model fails every time.
	#
	# worker-minimax is the best free model the benchmark has measured on trust:
	# 9 `autonomy` of 12 admissible runs on the OpenRouter route, G2 on 12 of 12
	# (Agents repo, `library/ai/models/minimax-openrouter.md`). It sits on OpenRouter's
	# shared `:free` pool, which is the pool the workspace can spend, and it is a
	# different pin from worker-nemotron-ultra, so the dispatch tiers stay separate.
	#
	# `dispatch` is a static lookup and cannot notice a dead model, so this will rot
	# again. When it does: probe the target with
	# `opencode run --model <route> "Reply with exactly: OK"` before repointing, and
	# repoint to a model the corpus has measured rather than to whichever console
	# preview answers — the console's free tier refuses per model, and its preview
	# models are withdrawn without notice.
	"general": "worker-minimax",
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
		ws = workspace_root()
		seen = load(RULE_CURSOR, {}).get(agent, {})
		files = [p for p in rule_files(ws) if file_hash(p) is not None]
		changed = [p for p in files if file_hash(p) != seen.get(p)]
		if not files:
			# A run that checked nothing must not read like a run that found no
			# changes. The first is a broken lookup, the second is the answer, and
			# an agent reading "no new guideline changes" stops looking.
			print("no rule files found in %s — nothing checked" % ws)
			return
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
	"""The checkout that owns `path`.

	A worktree's `.git` is a *file* naming the main repository's administrative
	directory, not a directory, so a lookup that recognises only a directory walks
	past the worktree root and settles on the repository that contains it. They are
	separate checkouts, and the worktree's own status is the one that says whether
	the file is dirty; the parent's status cannot see it at all.
	"""
	base = os.path.dirname(os.path.abspath(path))
	while True:
		if os.path.exists(os.path.join(base, ".git")):
			return base
		parent = os.path.dirname(base)
		if parent == base:
			return None
		base = parent

def repo_forms(repo, path):
	"""The path as the repository names it, and the name behind a symlink.

	A workspace root may hold a symlink to the tracked file it stands for
	(`STATUS.md` -> `personal/<person>/STATUS.md`), and git reports the tracked
	name, so a check that used the symlink's own name matched nothing and called a
	dirty file clean.
	"""
	forms = set()
	for candidate in (os.path.abspath(path), os.path.realpath(path)):
		try:
			forms.add(os.path.relpath(candidate, repo))
		except ValueError:
			pass
	return forms

def cmd_check_clean(args):
	abspaths = [os.path.abspath(p) for p in args.paths]
	if args.repo:
		repos = {os.path.realpath(args.repo): abspaths}
	else:
		repos = {}
		for p in abspaths:
			repos.setdefault(nearest_git(p) or p, []).append(p)
	blocked_all = []
	for repo, paths in repos.items():
		dirty = git_status(repo)
		if dirty is None:
			sys_stderr("%s is not a git repo (pass --repo)" % repo)
			raise SystemExit(2)
		want = set()
		for p in paths:
			want |= repo_forms(repo, p)
		for d in dirty:
			if any(under(w, d) for w in want):
				# One checkout names its files relative to itself; several would
				# name them the same way and mean different files, so the path
				# that says which checkout is the one that gets printed.
				blocked_all.append(d if len(repos) == 1 else os.path.join(repo, d))
	if not blocked_all:
		print("clean")
		return
	for d in sorted(set(blocked_all)):
		print("dirty %s" % d)
	raise SystemExit(1)

def main():
	parser = argparse.ArgumentParser(prog="agent-coord")
	sub = parser.add_subparsers(dest="command", required=True)
	sub.add_parser("id", help="print this agent's workspace-qualified id")
	sub.add_parser("note", help="(deprecated) print this agent's instance notes file path")
	sub.add_parser("instance-note", help="print this agent's instance notes file path")
	sub.add_parser("workspace", help="print this session's workspace root and tag")
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
	# Per-person operational files
	p = sub.add_parser("personal", help="manage per-person operational files")
	cp = p.add_subparsers(dest="personal_cmd", required=True)
	sp = cp.add_parser("whoami", help="resolve and print person id")
	sp.add_argument("--person", default=None, help="override person name")
	sp = cp.add_parser("path", help="print personal file path")
	sp.add_argument("file", nargs="?", default=None, help="file within personal dir")
	sp.add_argument("--person", default=None, help="override person name")
	sp = cp.add_parser("init", help="initialize personal files and root symlinks")
	sp.add_argument("--person", default=None, help="override person name")
	sp.add_argument("--root", default=None,
		help="workspace to scaffold (default: the caller's workspace; an installer passes its own)")
	sp.add_argument("--seed", choices=["current", "template"], default="template",
		help="seed from current root file or template (default: template)")
	sp.add_argument("--files", default="STATUS.md PLAN.md",
		help="space-separated list of files (default: STATUS.md PLAN.md)")
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
	 "workspace": cmd_workspace,
	 "news": cmd_news, "check-clean": cmd_check_clean, "dispatch": cmd_dispatch,
	 "role-note": cmd_role_note, "role-claim": cmd_role_claim,
	 "role-release": cmd_role_release, "role-status": cmd_role_status,
	 "personal": cmd_personal, "ctx": cmd_ctx}[args.command](args)

if __name__ == "__main__":
	main()
