#!/usr/bin/env python3
"""Append one entry to a HISTORY.md file, serializing concurrent appends.

HISTORY.md is append-only and is the most-written file in a workspace, so
two agents appending at once used to produce lost or interleaved lines.
This script takes an exclusive lock on the file for the whole read-check-write
so appends serialize across processes and machines sharing the filesystem.

Usage:
    history_append.py "body text" [--tag TAG] [--pointer PATH]
                      [--file PATH | --repo REPO] [--person NAME]

The entry is written in the file's existing format:

    - `<unix>` · <YYYY-MM-DD HH:MM:SS> · `<tag>` — <body>

Resolution of the target file:
    --file PATH            use this file verbatim.
    otherwise              <workspace>/personal/<person>/<repo>/HISTORY.md
                           if --repo names a repo other than the workspace's
                           own, else <workspace>/personal/<person>/HISTORY.md.
    <workspace> is the nearest ancestor holding a .agents directory.

Run from the Agents workspace with --repo XLib to append to XLib's history,
which lives there because XLib is public.
"""

import argparse,fcntl,os,subprocess,sys,time
from datetime import datetime

def nearest_workspace(base):
	base = os.path.realpath(base)
	while True:
		if os.path.isdir(os.path.join(base, ".agents")):
			return base
		parent = os.path.dirname(base)
		if parent == base:
			return None
		base = parent

def resolve_person(person_arg):
	if person_arg:
		return person_arg
	try:
		name = subprocess.check_output(
			["git", "-C", os.getcwd(), "config", "user.name"],
			stderr=subprocess.DEVNULL, text=True).strip()
		if name:
			return name
	except (subprocess.CalledProcessError, FileNotFoundError, OSError):
		pass
	name = os.environ.get("USER")
	if name:
		return name
	sys.stderr.write("no person id found; set --person or configure git config user.name\n")
	raise SystemExit(1)

def sanitize_person(pid):
	return pid.strip().replace(" ", "-")

def resolve_file(args):
	if args.file:
		return os.path.abspath(args.file)
	workspace = nearest_workspace(os.getcwd())
	if workspace is None:
		sys.stderr.write("no workspace (.agents) found; pass --file\n")
		raise SystemExit(1)
	person = sanitize_person(resolve_person(args.person))
	repo = args.repo or os.path.basename(workspace)
	person_dir = os.path.join(workspace, "personal", person)
	if repo and repo != os.path.basename(workspace):
		primary = os.path.join(person_dir, repo, "HISTORY.md")
	else:
		primary = os.path.join(person_dir, "HISTORY.md")
	if os.path.isfile(primary):
		return primary
	# fall back to the other candidate
	if primary == os.path.join(person_dir, "HISTORY.md"):
		alt = os.path.join(person_dir, repo, "HISTORY.md")
	else:
		alt = os.path.join(person_dir, "HISTORY.md")
	if os.path.isfile(alt):
		return alt
	# neither exists: create under the primary location
	return primary

def build_entry(tag, body, pointer):
	ts = int(time.time())
	dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	lines = body.split("\n")
	# strip a single trailing empty line
	if lines and lines[-1] == "":
		lines = lines[:-1]
	head = "- `%d` · %s · `%s` — %s" % (ts, dt, tag, lines[0] if lines else "")
	rest = []
	for line in lines[1:]:
		if line == "":
			rest.append("")
		elif line.startswith("\t"):
			rest.append(line)
		else:
			rest.append("\t" + line)
	parts = [head] + rest
	entry = "\n".join(parts)
	if pointer:
		entry = entry + " → " + pointer
	entry = entry + "\n"
	return entry

def main():
	parser = argparse.ArgumentParser(prog="history_append",
		description="Append one entry to a HISTORY.md file.")
	parser.add_argument("body", nargs="*", help="entry body (joined with spaces)")
	parser.add_argument("--body", dest="body_opt", default=None,
		help="entry body (may contain newlines)")
	parser.add_argument("--tag", default=None, help="scope tag (default: workspace/repo basename)")
	parser.add_argument("--pointer", default=None, help="optional doc pointer")
	parser.add_argument("--file", default=None, help="history file path")
	parser.add_argument("--repo", default=None, help="repo basename for resolution")
	parser.add_argument("--person", default=None, help="person id")
	args = parser.parse_args()

	if args.body_opt is not None:
		body = args.body_opt
	else:
		body = " ".join(args.body)
	if not body.strip():
		# allow stdin
		if not sys.stdin.isatty():
			body = sys.stdin.read()
	if not body.strip():
		sys.stderr.write("no entry body given\n")
		raise SystemExit(2)

	path = resolve_file(args)
	if args.tag:
		tag = args.tag
	elif args.repo:
		tag = args.repo
	else:
		ws = nearest_workspace(os.getcwd())
		tag = os.path.basename(ws) if ws else "agents"

	parent = os.path.dirname(path)
	if parent and not os.path.isdir(parent):
		os.makedirs(parent, exist_ok=True)
	if not os.path.isfile(path):
		sys.stderr.write("history file not found: %s\n" % path)
		raise SystemExit(1)

	entry = build_entry(tag, body, args.pointer)

	# Serialize appends across processes with an exclusive lock on the history
	# file itself. Locking the file being appended to (rather than a separate
	# lock file) means no lock file is created and left behind on disk, and
	# avoids the inode races that deleting a separate lock file would introduce.
	with open(path, "a+") as f:
		fcntl.flock(f.fileno(), fcntl.LOCK_EX)
		try:
			f.seek(0, os.SEEK_END)
			# ensure the file ends with a newline before appending
			if f.tell() > 0:
				f.seek(f.tell() - 1)
				last = f.read(1)
				if last != "\n":
					f.write("\n")
			f.write(entry)
			f.flush()
			os.fsync(f.fileno())
		finally:
			fcntl.flock(f.fileno(), fcntl.LOCK_UN)

	sys.stdout.write(entry)

if __name__ == "__main__":
	main()
