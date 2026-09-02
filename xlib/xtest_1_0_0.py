import importlib.util
import os,sys

def equal(a, b):
	if a != b:
		raise AssertionError(f"not equal: {a!r} != {b!r}")

def not_equal(a, b):
	if a == b:
		raise AssertionError(f"unexpectedly equal: {a!r}")

def same(a, b):
	if a is not b:
		raise AssertionError(f"not identical: {a!r} is not {b!r}")

def true(x):
	if not x:
		raise AssertionError(f"expected truthy, got {x!r}")

def raises(exc, fn):
	try:
		fn()
	except exc:
		return
	except Exception as e:
		msg = f"expected {exc.__name__}, got {type(e).__name__}: {e}"
		raise AssertionError(msg) from e
	raise AssertionError(f"expected {exc.__name__}, but nothing raised")

def contains(item, container):
	if item not in container:
		raise AssertionError(f"{item!r} not in {container!r}")

def kind(value, kind_):
	if not isinstance(value, kind_):
		msg = f"expected {kind_.__name__}, got {type(value).__name__}"
		raise AssertionError(msg)

_registry = []

def test(fn):
	_registry.append(fn)
	return fn

def _run_funcs(funcs):
	passed = failed = 0
	for fn in funcs:
		try:
			fn()
		except Exception as e:
			failed += 1
			print(f"FAIL {fn.__module__}.{fn.__name__}: {e}")
		else:
			passed += 1
			print(f"pass {fn.__module__}.{fn.__name__}")
	return passed, failed

def _load_dir(directory):
	funcs = []
	for path in sorted(os.listdir(directory)):
		if not path.startswith("test_") or not path.endswith(".py"):
			continue
		full = os.path.join(directory, path)
		name = path[:-3]
		spec = importlib.util.spec_from_file_location(name, full)
		mod = importlib.util.module_from_spec(spec)
		sys.modules["xtest"] = sys.modules[__name__]
		sys.path.insert(0, directory)
		try:
			spec.loader.exec_module(mod)
		finally:
			sys.path.remove(directory)
		for attr in sorted(dir(mod)):
			if attr.startswith("test_"):
				fn = getattr(mod, attr)
				if callable(fn):
					funcs.append(fn)
	return funcs

def run(target=None):
	if target is None:
		funcs = list(_registry)
	elif os.path.isdir(str(target)):
		funcs = _load_dir(str(target))
	elif os.path.isfile(str(target)):
		funcs = _load_dir(os.path.dirname(str(target)))
	else:
		msg = f"invalid target: {target!r}"
		raise ValueError(msg)
	passed, failed = _run_funcs(funcs)
	print(f"{passed} passed, {failed} failed")
	if failed:
		return 1
	return 0
