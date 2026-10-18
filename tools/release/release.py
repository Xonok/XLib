import argparse,io,os,re,subprocess,sys,tempfile,time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from tools.pybundle import bundler

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

def bundled(entry):
	"""The bundle for an entry file, as text.

	**The bridge lives here and not in the bundler**, because the human ruled
	2026-10-17 to keep the spec as written — its seven functions end at
	`main(entry, out)`, and `bundle(entry) -> str` is not among them. `main` takes a
	file-like sink and never closes it (R5), so a buffer in and `.getvalue()` out
	is the whole of the adaptation.
	"""
	sink = io.StringIO()
	bundler.main(str(entry), sink)
	return sink.getvalue()

def linted(text, beside):
	"""What this repository's xlint says about a bundle, and whether it passes.

	**The gate belongs here and not to the bundler** (D37). The bundler's own rule
	is narrower — it adds no findings of its own and passes through whatever the
	source already had — so what arrives at a release may carry a finding the source
	had, and this repository does not release those. The bundler has to stay open
	enough to bundle a project this repository's style does not govern.

	Run the same way the pre-commit hook runs it, by invocation rather than by
	import, so the gate and the hook cannot drift. The text is checked through a
	temporary file **beside the release target** rather than on the target, so a
	refusal leaves nothing in `xlib/` — which this folder's README warns about.
	"""
	probe = tempfile.NamedTemporaryFile("w", suffix = ".py", prefix = "release-check-",
		dir = beside, delete = False, encoding = "utf-8")
	try:
		probe.write(text)
		probe.close()
		found = subprocess.run([sys.executable, str(ROOT / "tools" / "xlint" / "xlint.py"), probe.name],
			capture_output = True, text = True)
		return found.returncode, found.stdout.strip()
	finally:
		os.unlink(probe.name)

def release(library, bump, force):
	if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", library) is None:
		msg = f"not a valid library name: {library!r}"
		raise ValueError(msg)
	devdir = ROOT / "dev" / library
	entry = devdir / f"{library}.py"
	if not entry.is_file():
		msg = f"no entry point {entry}: each library lives in dev/{library}/{library}.py"
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
	text = bundled(entry)
	code, said = linted(text, target.parent)
	if code != 0:
		raise ValueError(f"the bundle is not xlint-clean, and nothing this repository releases is:\n{said}")
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
