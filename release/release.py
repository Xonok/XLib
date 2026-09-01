import argparse,ast,io,re,sys,time,token,tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pybundle import bundler

_VERSION_RE = re.compile(r"^(.+?)_(\d+)_(\d+)_(\d+)\.py$")

# Majors need the previous major to sit for a while first; tune this or use --force.
_MAJOR_MIN_AGE_MONTHS = 12

def line_offsets(text):
	res = [0]
	for i, ch in enumerate(text):
		if ch == "\n":
			res.append(i + 1)
	return res

def tokenize_text(text):
	return list(tokenize.generate_tokens(io.StringIO(text).readline))

def released_versions(library):
	res = []
	for path in (ROOT / "xlib").glob(f"{library}_*.py"):
		m = _VERSION_RE.match(path.name)
		if m is not None and m.group(1) == library:
			res.append((int(m.group(2)), int(m.group(3)), int(m.group(4))))
	return sorted(res)

def latest_release(library):
	vers = released_versions(library)
	return vers[-1] if vers else None

def release_path(library, version):
	major, minor, revision = version
	return ROOT / "xlib" / f"{library}_{major}_{minor}_{revision}.py"

def next_version(version, bump):
	major, minor, revision = version
	if bump == "minor":
		return (major, minor + 1, 0)
	if bump == "major":
		return (major + 1, 0, 0)
	return (major, minor, revision + 1)

def read_pins(devdir):
	path = devdir / "xlib_pins.py"
	if not path.is_file():
		return {}
	tree = ast.parse(path.read_text())
	for node in tree.body:
		if isinstance(node, ast.Assign):
			for target in node.targets:
				if isinstance(target, ast.Name) and target.id == "PIN":
					pins = ast.literal_eval(node.value)
					if isinstance(pins, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in pins.items()):
						return pins
					msg = f"PIN in {path} must map strings to strings"
					raise ValueError(msg)
	return {}

def resolve_import(name, pins, missing):
	if _VERSION_RE.match(f"{name}.py") is not None:
		if (ROOT / "xlib" / f"{name}.py").is_file():
			return name
		missing.append(name)
		return None
	if name in pins:
		full = f"{name}_{pins[name]}"
		if (ROOT / "xlib" / f"{full}.py").is_file():
			return full
		missing.append(full)
		return None
	latest = latest_release(name)
	if latest is None:
		missing.append(name)
		return None
	return f"{name}_{latest[0]}_{latest[1]}_{latest[2]}"

def rewrite_imports(text, resolve):
	lengths = line_offsets(text)
	toks = tokenize_text(text)
	repls = []
	i = 0
	while i < len(toks):
		t = toks[i]
		if t.type != token.NAME or t.string != "from" or i + 2 >= len(toks):
			i += 1
			continue
		if toks[i + 1].type != token.NAME or toks[i + 1].string != "xlib":
			i += 1
			continue
		if toks[i + 2].type != token.NAME or toks[i + 2].string != "import":
			i += 1
			continue
		j = i + 3
		entries = []
		end = None
		bad = False
		while j < len(toks) and toks[j].type not in (token.NEWLINE, token.NL, token.ENDMARKER):
			tt = toks[j]
			if tt.type == token.COMMENT:
				break
			if tt.type != token.NAME:
				bad = True
				break
			src = tt.string
			j += 1
			end = tt.end
			alias = None
			if j < len(toks) and toks[j].type == token.NAME and toks[j].string == "as":
				j += 1
				if j < len(toks) and toks[j].type == token.NAME:
					alias = toks[j].string
					end = toks[j].end
					j += 1
				else:
					bad = True
					break
			entries.append((src, alias))
			if j < len(toks) and toks[j].type == token.OP and toks[j].string == ",":
				j += 1
				continue
			break
		if not bad:
			parts = []
			for src, alias in entries:
				new = resolve(src)
				if new is None:
					bad = True
					break
				parts.append(f"{new} as {alias or src}")
		if not bad and parts:
			start = lengths[t.start[0] - 1] + t.start[1]
			oldend = lengths[end[0] - 1] + end[1]
			new = "from xlib import " + ", ".join(parts)
			if text[start:oldend] != new:
				repls.append((start, oldend, new))
		i = j + 1
	for start, oldend, new in sorted(repls, reverse=True):
		text = text[:start] + new + text[oldend:]
	return text

def check_major_age(library, latest, force):
	if force:
		return
	path = release_path(library, latest)
	first_of_line = ROOT / "xlib" / f"{library}_{latest[0]}_0_0.py"
	if first_of_line.is_file():
		path = first_of_line
	months = (time.time() - path.stat().st_mtime) / (30.44 * 86400)
	if months < _MAJOR_MIN_AGE_MONTHS:
		msg = f"refusing major: the previous major is only {months:.1f} months old; majors need at least {_MAJOR_MIN_AGE_MONTHS} months (--force overrides)"
		raise ValueError(msg)

def release(library, bump, force):
	if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", library) is None:
		msg = f"not a valid library name: {library!r}"
		raise ValueError(msg)
	devdir = ROOT / library
	entry = devdir / f"{library}.py"
	if not entry.is_file():
		msg = f"no entry point {entry}: each library lives in {library}/{library}.py"
		raise ValueError(msg)
	latest = latest_release(library)
	if latest is None:
		if bump != "rev":
			msg = f"{library} has no release yet; the first release is always 1_0_0"
			raise ValueError(msg)
		version = (1, 0, 0)
	else:
		version = next_version(latest, bump)
		if bump == "major":
			check_major_age(library, latest, force)
	pins = read_pins(devdir)
	missing = []
	used = []
	def resolve(name):
		full = resolve_import(name, pins, missing)
		if full is not None:
			used.append(full)
		return full
	text = rewrite_imports(bundler.bundle(str(entry)), resolve)
	if missing:
		names = ", ".join(dict.fromkeys(missing))
		msg = f"cannot release {library}: requirement(s) have no release: {names}"
		raise ValueError(msg)
	target = release_path(library, version)
	if target.is_file():
		msg = f"{target.name} already exists in xlib/"
		raise ValueError(msg)
	target.write_text(text)
	pins_info = f" (pins: {', '.join(dict.fromkeys(used))})" if used else ""
	print(f"released {target.name}{pins_info}")

def main(argv=None):
	ap = argparse.ArgumentParser(description="Release a dev library into xlib/.")
	ap.add_argument("library", help="library name; the dev folder must be <library>/<library>.py")
	flags = ap.add_mutually_exclusive_group()
	flags.add_argument("--minor", action="store_true", help="bump the minor version, resetting revision to 0")
	flags.add_argument("--major", action="store_true", help="bump the major version, resetting minor and revision to 0")
	ap.add_argument("--force", action="store_true", help="skip the major-release age gate")
	args = ap.parse_args(argv)
	bump = "major" if args.major else "minor" if args.minor else "rev"
	try:
		release(args.library, bump, args.force)
	except ValueError as e:
		print(f"release: {e}", file=sys.stderr)
		sys.exit(1)

if __name__ == "__main__":
	main()
