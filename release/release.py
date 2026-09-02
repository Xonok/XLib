import argparse,re,sys,time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pybundle import bundler

_VERSION_RE = re.compile(r"^(.+?)_(\d+)_(\d+)_(\d+)\.py$")

# Majors need the previous major to sit for a while first; tune this or use --force.
_MAJOR_MIN_AGE_MONTHS = 12

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
	target = release_path(library, version)
	if target.is_file():
		msg = f"{target.name} already exists in xlib/"
		raise ValueError(msg)
	text = bundler.bundle(str(entry))
	target.write_text(text)
	print(f"released {target.name}")

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
