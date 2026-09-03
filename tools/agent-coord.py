import argparse,fcntl,glob,hashlib,json,os,sys
from contextlib import contextmanager

SLOTS = ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".agents")
LOCK = os.path.join(DIR, "lock")
IDS = os.path.join(DIR, "ids.json")
CLAIMS = os.path.join(DIR, "claims.json")
ROTATION_CURSOR = os.path.join(DIR, "rotation.json")
ROTATION = ["worker-mimo", "worker-nemotron-lightning", "worker-nemotron-ultra", "worker-ling"]
RULE_CURSOR = os.path.join(DIR, "rule-cursor.json")

def rule_files():
	paths = [os.path.join(ROOT, "AGENTS.md")]
	paths += sorted(glob.glob(os.path.join(ROOT, ".opencode", "agent", "*.md")))
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

def session_key():
	name = os.environ.get("OPENCODE_AGENT_ID")
	if name:
		return name
	pid = os.getpid()
	while True:
		with open("/proc/%s/stat" % pid) as f:
			parts = f.read().split()
		comm = parts[1].strip("()")
		ppid = int(parts[3])
		if comm == "opencode":
			return "pid-%s" % pid
		if pid in (1, ppid):
			return "pid-%s" % os.getpid()
		pid = ppid

def my_id():
	key = session_key()
	if not key.startswith("pid-"):
		return key
	with locked():
		recycle_dead_slots()
		ids = load(IDS, {})
		if key in ids:
			return ids[key]
		taken = set(ids.values())
		free = [s for s in SLOTS if s not in taken]
		if not free:
			sys_stderr("no free agent slot (limit %s, %s in use); set OPENCODE_AGENT_ID to pick one" % (len(SLOTS), len(taken)))
			raise SystemExit(1)
		slot = free[0]
		ids[key] = slot
		save(IDS, ids)
		return slot

def sys_stderr(msg):
	print(msg, file=sys.stderr)

def is_process_alive(pid):
	"""Check if a process with the given PID is still running."""
	return os.path.exists("/proc/%s" % pid)

def recycle_dead_slots():
	"""Remove ids.json entries for processes that no longer exist, freeing their slots."""
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
		slot = ids[key]
		ids.pop(key, None)
		claims.pop(slot, None)
		cursors.pop(slot, None)
	if dead_keys:
		save(IDS, ids)
		save(CLAIMS, claims)
		save(RULE_CURSOR, cursors)

def note_path(agent):
	return os.path.join(DIR, "agent-notes-%s.md" % agent)

def claim_paths(paths):
	return [os.path.abspath(p) for p in paths]

def cmd_id(args):
	print(my_id())

def cmd_note(args):
	print(note_path(my_id()))

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

def cmd_rotation(args):
	with locked():
		cursor = load(ROTATION_CURSOR, 0)
		if args.position:
			print(cursor % len(ROTATION))
		elif args.next:
			model = ROTATION[cursor % len(ROTATION)]
			save(ROTATION_CURSOR, cursor + 1)
			print(model)
		else:
			print(ROTATION[cursor % len(ROTATION)])

def cmd_news(args):
	agent = my_id()
	with locked():
		seen = load(RULE_CURSOR, {}).get(agent, {})
		files = [p for p in rule_files() if file_hash(p) is not None]
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

def main():
	parser = argparse.ArgumentParser(prog="agent-coord")
	sub = parser.add_subparsers(dest="command", required=True)
	sub.add_parser("id", help="print this agent's id")
	sub.add_parser("note", help="print this agent's notes file path")
	p = sub.add_parser("claim", help="claim files before editing")
	p.add_argument("paths", nargs="+")
	p.add_argument("--force", action="store_true", help="steal files held by the other agent")
	p = sub.add_parser("release", help="release claimed files")
	p.add_argument("paths", nargs="+")
	sub.add_parser("release-all", help="release everything this agent claimed")
	sub.add_parser("status", help="show who holds what")
	p = sub.add_parser("rotation", help="show or advance the shared subagent rotation cursor")
	p.add_argument("--next", action="store_true", help="advance the cursor and print the model to dispatch now")
	p.add_argument("--position", action="store_true", help="print the current cursor position without a model name")
	p = sub.add_parser("news", help="report rule-file changes since this agent last looked (and mark them seen)")
	p.add_argument("--peek", action="store_true", help="report changes without marking them seen")
	p.add_argument("--status", action="store_true", help="print caught-up status without changing anything")
	args = parser.parse_args()
	{"id": cmd_id, "note": cmd_note, "claim": cmd_claim, "release": cmd_release,
	 "release-all": cmd_release_all, "status": cmd_status, "rotation": cmd_rotation,
	 "news": cmd_news}[args.command](args)

if __name__ == "__main__":
	main()
