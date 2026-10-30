#!/usr/bin/env python3
"""ruffwatch — watch-mode runner for ruff with per-file result caching.

Runs `ruff check` in a terminal pane the way xlint --watch does: normal
screen (so scrollback keeps the last report), cursor hidden while watching.
Unchanged files are not re-checked: a file whose mtime and size match the
cache keeps its previous findings.  ruff is largely per-file, so this is
safe; pass --full to force a complete re-run (for cross-file tools or after
a config change you want to be sure about).

Usage:
    ruffwatch [paths...] [--full] [--interval SECONDS]
"""

import argparse,ctypes,errno,hashlib,json,os,select,signal,struct,subprocess,sys,termios,time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_POLL = 0.2
_CLEAR = "\033[H\033[2J\033[3J"
_HIDE = "\033[?25l"
_SHOW = "\033[?25h"
_INOTIFY_MASK = 0x00000008 | 0x00000040 | 0x00000080 | 0x00000100 | 0x00000200 | 0x00000400 | 0x00000800
_EVENT = struct.Struct("=iIII")
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
except (AttributeError, OSError):
	_libc = None

_CONFIG_NAMES = ("pyproject.toml", "ruff.toml", ".ruff.toml")

def _ruff_files(paths):
	"""Ask ruff which files it would check (honours its own config/excludes)."""
	out = subprocess.run(
		["ruff", "check", "--show-files", *paths],
		capture_output=True, text=True,
	)
	files = []
	for line in out.stdout.splitlines():
		line = line.strip()
		if line:
			files.append(Path(line))
	return sorted(set(files))

def _config_stamp(paths):
	"""A cheap signature of the ruff config in force, or None if none found."""
	root = Path(paths[0] if paths else ".").resolve()
	# search upward-ish: just check the given roots and cwd
	candidates = []
	for p in list(paths) + ["."]:
		base = Path(p).resolve()
		for name in _CONFIG_NAMES:
			f = base / name
			if f.is_file():
				candidates.append(f)
			# also cwd
	cwd = Path.cwd()
	for name in _CONFIG_NAMES:
		f = cwd / name
		if f.is_file() and f not in candidates:
			candidates.append(f)
	h = hashlib.sha256()
	found = False
	for f in sorted(set(candidates)):
		try:
			st = f.stat()
			h.update(str(f).encode())
			h.update(str(st.st_mtime_ns).encode())
			h.update(str(st.st_size).encode())
			found = True
		except OSError:
			pass
	return h.hexdigest() if found else None

def _run_ruff(files):
	"""Run ruff on `files`, return (list of finding dicts, ok)."""
	if not files:
		return [], True
	cmd = ["ruff", "check", "--output-format", "json", *map(str, files)]
	res = subprocess.run(cmd, capture_output=True, text=True)
	try:
		data = json.loads(res.stdout) if res.stdout.strip() else []
	except json.JSONDecodeError:
		data = []
	if not isinstance(data, list):
		data = []
	return data, res.returncode == 0

def _render(findings):
	sys.stdout.write(_CLEAR)
	if not findings:
		print("ruff: no findings. Watching for file changes.")
		return
	# group by file for stable output
	by_file = {}
	for f in findings:
		by_file.setdefault(f.get("filename", "?"), []).append(f)
	for fn in sorted(by_file):
		for f in sorted(by_file[fn], key=lambda x: (x.get("row", 0), x.get("column", 0))):
			code = f.get("code", "")
			msg = f.get("message", "")
			loc = f.get("location") or {}
			row = loc.get("row", 0)
			col = loc.get("column", 0)
			print(f"{fn}:{row}:{col}: {code} {msg}".rstrip())
	print(f"\n{len(findings)} finding(s). Watching for file changes.")

def _watch_dirs(root):
	"""Recursively list directories under root (excluding heavy/hidden-ish ones)."""
	skip = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
	result = []
	for dirpath, dirnames, _ in os.walk(root):
		dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".git")]
		result.append(Path(dirpath))
	return result

def main():
	ap = argparse.ArgumentParser(description="ruff watch mode with per-file caching")
	ap.add_argument("paths", nargs="*", default=["."])
	ap.add_argument("--full", action="store_true", help="force a full re-run, ignore cache")
	ap.add_argument("--interval", type=float, default=0.5)
	args = ap.parse_args()

	files = _ruff_files(args.paths)
	# cache: path -> (mtime_ns, size, findings_list)
	cache = {}
	config_sig = _config_stamp(args.paths)

	# initial full run
	data, _ = _run_ruff(files)
	for f in files:
		cache[f] = None # placeholder until grouped
	# group findings by file
	by_file = {f: [] for f in files}
	for finding in data:
		fn = finding.get("filename")
		if fn is not None:
			by_file.setdefault(Path(fn), []).append(finding)
	for f in files:
		try:
			st = f.stat()
			cache[f] = (st.st_mtime_ns, st.st_size, by_file.get(f, []))
		except OSError:
			cache[f] = (0, 0, by_file.get(f, []))

	# inotify setup (best effort)
	fd = None
	wd_to_dir = {}
	if _libc is not None:
		try:
			fd = _libc.inotify_init()
			if fd != -1:
				for d in _watch_dirs(args.paths[0] if args.paths else "."):
					wd = _libc.inotify_add_watch(fd, os.fsencode(d), _INOTIFY_MASK)
					if wd != -1:
						wd_to_dir[wd] = d
			else:
				fd = None
		except OSError:
			fd = None

	# terminal: hide cursor, restore on exit
	stdin_fd = None
	old_attrs = None
	if sys.stdin.isatty():
		try:
			stdin_fd = sys.stdin.fileno()
			old_attrs = termios.tcgetattr(stdin_fd)
			new_attrs = termios.tcgetattr(stdin_fd)
			new_attrs[3] &= ~(termios.ECHO | getattr(termios, "ECHOCTL", 0))
			termios.tcsetattr(stdin_fd, termios.TCSANOW, new_attrs)
		except (termios.error, OSError):
			stdin_fd = None
			old_attrs = None

	def restore():
		if stdin_fd is not None and old_attrs is not None:
			try:
				termios.tcsetattr(stdin_fd, termios.TCSANOW, old_attrs)
			except termios.error:
				pass
		sys.stdout.write(_SHOW)
		sys.stdout.flush()

	signal.signal(signal.SIGINT, lambda *_: (restore(), sys.exit(0)))
	signal.signal(signal.SIGTERM, lambda *_: (restore(), sys.exit(0)))

	try:
		sys.stdout.write(_HIDE)
		sys.stdout.flush()
		# initial render
		all_findings = []
		for f in files:
			all_findings.extend(cache.get(f, (0, 0, []))[2] if cache.get(f) else [])
		_render(all_findings)

		last_config = config_sig
		while True:
			# wait for change trigger
			triggered = False
			if fd is not None:
				ready, _, _ = select.select([fd], [], [], args.interval)
				if ready:
					try:
						os.read(fd, 65536)
					except OSError:
						pass
					triggered = True
				# also periodic poll fallback
			# check mtimes
			new_config = _config_stamp(args.paths)
			config_changed = new_config != last_config
			if config_changed:
				last_config = new_config
				# invalidate cache
				cache.clear()
				config_changed = True

			changed = []
			current_files = _ruff_files(args.paths)
			# new files
			for f in current_files:
				if f not in cache:
					changed.append(f)
			# removed files
			for f in list(cache.keys()):
				if f not in current_files:
					del cache[f]
			# mtime checks
			for f in current_files:
				if f in cache and cache[f] is not None:
					try:
						st = f.stat()
					except OSError:
						changed.append(f)
						continue
					if st.st_mtime_ns != cache[f][0] or st.st_size != cache[f][1]:
						changed.append(f)
				else:
					changed.append(f)

			if not changed and not triggered and not config_changed:
				# nothing to do this pass
				continue

			if args.full or config_changed:
				run_files = list(current_files)
			elif changed:
				run_files = changed
			else:
				run_files = []

			if run_files:
				data, _ = _run_ruff(run_files)
				by_file = {f: [] for f in run_files}
				for finding in data:
					fn = finding.get("filename")
					if fn is not None:
						by_file.setdefault(Path(fn), []).append(finding)
				for f in run_files:
					try:
						st = f.stat()
						cache[f] = (st.st_mtime_ns, st.st_size, by_file.get(f, []))
					except OSError:
						cache[f] = (0, 0, by_file.get(f, []))

			files = current_files
			all_findings = []
			for f in files:
				entry = cache.get(f)
				if entry is not None:
					all_findings.extend(entry[2])
				else:
					all_findings.extend([])
			_render(all_findings)
	finally:
		restore()
		if fd is not None:
			try:
				os.close(fd)
			except OSError:
				pass

if __name__ == "__main__":
	main()
