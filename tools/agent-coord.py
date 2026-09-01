import argparse,fcntl,json,os,sys
from contextlib import contextmanager

SLOTS = ["a1", "a2"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".agents")
LOCK = os.path.join(DIR, "lock")
IDS = os.path.join(DIR, "ids.json")
CLAIMS = os.path.join(DIR, "claims.json")

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
	args = parser.parse_args()
	{"id": cmd_id, "note": cmd_note, "claim": cmd_claim, "release": cmd_release,
	 "release-all": cmd_release_all, "status": cmd_status}[args.command](args)

if __name__ == "__main__":
	main()
