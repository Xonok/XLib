import importlib,re,sys
from pathlib import Path

_VERSION_RE = re.compile(r"^(.+?)_(\d+)_(\d+)_(\d+)\.py$")
_LIBRARY_DIR = Path(__file__).parent

def _versioned_files():
	found = {}
	for path in _LIBRARY_DIR.glob("*.py"):
		m = _VERSION_RE.match(path.name)
		if m is None:
			continue
		base = m.group(1)
		version = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
		found.setdefault(base, []).append((version, path.name))
	return found

def _pinned_versions():
	try:
		pins = importlib.import_module("xlib_pins")
		return {name: str(version) for name, version in getattr(pins, "PIN", {}).items()}
	except ImportError:
		return {}

def _resolve(name, files):
	vm = _VERSION_RE.match(f"{name}.py")
	if vm is not None:
		version = (int(vm.group(2)), int(vm.group(3)), int(vm.group(4)))
		for v, _ in files.get(vm.group(1), []):
			if v == version:
				return name
		return None
	pins = _pinned_versions()
	if name in pins:
		return f"{name}_{pins[name]}"
	versions = files.get(name)
	if not versions:
		return None
	version = max(versions, key=lambda pair: pair[0])[0]
	return f"{name}_{version[0]}_{version[1]}_{version[2]}"

def __getattr__(name):
	if name.startswith("_"):
		raise AttributeError(f"module 'xlib' has no attribute '{name}'")
	files = _versioned_files()
	versioned = _resolve(name, files)
	if versioned is None:
		raise AttributeError(f"module 'xlib' has no attribute '{name}'")
	module = importlib.import_module(f"xlib.{versioned}")
	# resolve the plain name to this module so repeated imports skip re-resolution
	sys.modules[f"xlib.{name}"] = module
	return module
