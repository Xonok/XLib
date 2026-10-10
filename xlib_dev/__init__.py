"""Stand-ins for the released libraries, backed by the versions in `dev/`.

`from xlib_dev import xcsv` yields the same names as `from xlib import xcsv`,
but loaded from `dev/xcsv/` rather than the newest file in `xlib/`. Use it to
run real code against a library that has not been released yet, and drop back
to `xlib` once the release it needs exists.

The override covers the import a caller makes. It does not redirect the
imports a library makes for itself: those are pinned to released versions by
design, so a dev library under test still gets released versions of whatever
it depends on.
"""
import importlib,sys
from pathlib import Path

_DEV_DIR = Path(__file__).parent.parent / "dev"

def _library_names():
	"""The libraries with a dev folder to stand in for, sorted; empty if `dev/` is missing."""
	if not _DEV_DIR.is_dir():
		return []
	found = []
	for path in _DEV_DIR.iterdir():
		if path.is_dir() and (path / f"{path.name}.py").is_file():
			found.append(path.name)
	return sorted(found)

def __getattr__(name):
	"""Return `dev/<name>/<name>.py` as an attribute of this package."""
	if name.startswith("_"):
		raise AttributeError(f"module 'xlib_dev' has no attribute '{name}'")
	available = _library_names()
	if name not in available:
		raise AttributeError(f"module 'xlib_dev' has no attribute '{name}'; available: {', '.join(available) or 'none'}")
	module = importlib.import_module(f"dev.{name}.{name}")
	# the library keeps its own module name, so its relative imports still resolve
	sys.modules[f"xlib_dev.{name}"] = module
	return module

def __dir__():
	"""The libraries to override; this package's own internals are not part of its surface."""
	return _library_names()
