"""Tests for the `xlib_dev` override: a caller's import lands on `dev/`, not `xlib/`."""
import os,sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
	sys.path.insert(0, _ROOT)

import xlib_dev
from dev.xtest.xtest import contains,equal,not_equal,raises,same,true

_LIBRARY_NAMES = ["xconf", "xcsv", "xprod", "xschema", "xtest"]
_xcsv = getattr(xlib_dev, "xcsv")

def _released(name):
	return __import__("xlib").__getattr__(name)

def _ends_with(suffix, path):
	return path.replace("\\", "/").endswith(suffix)

def test_listing_names_every_dev_library():
	equal(sorted(xlib_dev._library_names()), _LIBRARY_NAMES)

def test_dir_shows_libraries_and_not_internals():
	equal(dir(xlib_dev), _LIBRARY_NAMES)

def test_override_resolves_to_the_dev_file():
	true(_ends_with("/dev/xcsv/xcsv.py", _xcsv.__file__))

def test_library_keeps_its_own_module_name():
	equal(_xcsv.__name__, "dev.xcsv.xcsv")

def test_library_relative_imports_still_resolve():
	true(hasattr(_xcsv, "csv_tok"))

def test_repeated_access_is_the_same_module():
	same(getattr(xlib_dev, "xcsv"), _xcsv)

def test_override_is_not_the_released_library():
	not_equal(_xcsv.__file__, _released("xcsv").__file__)

def test_override_carries_dev_internals_the_release_does_not():
	true("csv_tok" in dir(_xcsv) and "csv_tok" not in dir(_released("xcsv")))

def test_unknown_library_raises():
	raises(AttributeError, lambda: xlib_dev.nosuchlibrary)

def test_private_name_raises():
	raises(AttributeError, lambda: xlib_dev._nosuchlibrary)

def test_unknown_library_error_lists_what_is_available():
	try:
		xlib_dev.nosuchlibrary
	except AttributeError as e:
		contains("xcsv", str(e))
	else:
		raise AssertionError("expected AttributeError for an unknown library")

def test_no_released_file_references_the_override():
	released_dir = os.path.join(_ROOT, "xlib")
	offenders = []
	for name in os.listdir(released_dir):
		if not name.endswith(".py"):
			continue
		with open(os.path.join(released_dir, name)) as f:
			if "xlib_dev" in f.read():
				offenders.append(name)
	equal(offenders, [])

if __name__ == "__main__":
	from dev.xtest.xtest import run
	sys.exit(run(__file__))
