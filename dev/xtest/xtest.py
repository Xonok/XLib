"""xtest — a lightweight test runner with assertion helpers.

A test is a function that raises on failure. It can be written four ways, and
xtest runs all four:

- a plain function named `test_*`,
- a function decorated with `@xtest.test` (any name),
- a method of an `xtest.TestCase` subclass, with `setUp`/`tearDown`,
- a method of a `unittest.TestCase` subclass, which xtest runs through
	unittest's own machinery so `addCleanup`, `subTest` and the skip decorators
	keep working.

The runner is the point of the library as much as the assertions are: a suite
that cannot be run is a suite that does not exist, and one that cannot be run
by the obvious command is worse than one that fails loudly.
"""
import importlib.util,inspect,os,sys,traceback,unittest

def _short(value, limit = 200):
	"""A value, cut short.

	A failure message that quotes a whole file is unreadable, and the one
	thing it has to say is which needle was not in which haystack.
	"""
	text = repr(value)
	if len(text) <= limit:
		return text
	return text[:limit] + f"... ({len(text)} chars)"

def _with(message, text):
	"""The assertion's message, with the caller's own appended when there is one.

	A suite of nine hundred tests cannot be read one failure at a time, so a
	failure has to say what was being checked.
	"""
	if message:
		return f"{text} -- {message}"
	return text

def equal(a, b, message = None):
	if a != b:
		raise AssertionError(_with(message, f"not equal: {a!r} != {b!r}"))

def not_equal(a, b, message = None):
	if a == b:
		raise AssertionError(_with(message, f"unexpectedly equal: {a!r}"))

def same(a, b, message = None):
	if a is not b:
		raise AssertionError(_with(message, f"not identical: {a!r} is not {b!r}"))

def true(x, message = None):
	if not x:
		raise AssertionError(_with(message, f"expected truthy, got {x!r}"))

def raises(exc, fn, message = None):
	try:
		fn()
	except exc:
		return
	except Exception as e:
		msg = _with(message, f"expected {exc.__name__}, got {type(e).__name__}: {e}")
		raise AssertionError(msg) from e
	raise AssertionError(_with(message, f"expected {exc.__name__}, but nothing raised"))

def contains(item, container, message = None):
	if item not in container:
		raise AssertionError(_with(message, f"{item!r} not in {_short(container)}"))

def kind(value, kind_, message = None):
	if not isinstance(value, kind_):
		msg = _with(message, f"expected {kind_.__name__}, got {type(value).__name__}")
		raise AssertionError(msg)

class TestCase:
	"""A test case with `setUp`, `tearDown` and the assertions as methods.

	Each test method gets a fresh instance, so one test's state cannot reach
	another's. `setUp` and `tearDown` are optional and default to doing
	nothing.
	"""

	def setUp(self):
		pass

	def tearDown(self):
		pass

	def equal(self, a, b, message = None):
		equal(a, b, message)

	def not_equal(self, a, b, message = None):
		not_equal(a, b, message)

	def same(self, a, b, message = None):
		same(a, b, message)

	def true(self, x, message = None):
		true(x, message)

	def raises(self, exc, fn, message = None):
		raises(exc, fn, message)

	def contains(self, item, container, message = None):
		contains(item, container, message)

	def kind(self, value, kind_, message = None):
		kind(value, kind_, message)

_registry = []

def test(fn):
	_registry.append(fn)
	return fn

def _requires_arguments(fn):
	"""True for a callable that cannot be called with no arguments.

	A module-level `test_*` function that needs arguments is a mistake — it is
	a method that lost its class, or a helper that was given a test's name.
	Reporting it is the point: skipping it quietly would be the same failure
	mode as a suite that cannot be run, one level down.
	"""
	try:
		signature = inspect.signature(fn)
	except (TypeError, ValueError):
		return False
	for param in signature.parameters.values():
		if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
			if param.default is param.empty:
				return True
	return False

def _test_methods(cls):
	"""The `test_*` methods of a class, in a stable order."""
	out = []
	for name in sorted(dir(cls)):
		if not name.startswith("test_"):
			continue
		attr = getattr(cls, name, None)
		if callable(attr):
			out.append(name)
	return out

class _Outcome(unittest.TestResult):
	"""A unittest result that keeps each test's outcome, in order.

	unittest's own result keeps failures and errors, but not the passes, and a
	runner that reports every test needs the passes too.
	"""

	def __init__(self):
		super().__init__()
		self.outcomes = []

	def addSuccess(self, test):
		super().addSuccess(test)
		self.outcomes.append(("pass", _label(test), None))

	def addFailure(self, test, err):
		super().addFailure(test, err)
		self.outcomes.append(("fail", _label(test), self._exc_info_to_string(err, test)))

	def addError(self, test, err):
		super().addError(test, err)
		self.outcomes.append(("fail", _label(test), self._exc_info_to_string(err, test)))

	def addSkip(self, test, reason):
		super().addSkip(test, reason)
		self.outcomes.append(("skip", _label(test), reason))

def _label(test):
	"""The name of a unittest test: module, class and method."""
	cls = type(test)
	return f"{cls.__module__}.{cls.__name__}.{test._testMethodName}"

class _Group:
	"""The tests of one file, kept together.

	One file is one group because a module's fixtures — `setUpModule` and
	`tearDownModule` — belong to that module's tests and to no others.
	"""

	def __init__(self, path, mod):
		self.path = path
		self.mod = mod
		self.plain = []
		self.xtest_cases = []
		self.unittest_cases = []
		self.broken = []
		self._collect()

	def _collect(self):
		own = self.mod.__name__
		for name in sorted(dir(self.mod)):
			if not name.startswith("test_"):
				continue
			obj = getattr(self.mod, name, None)
			if not callable(obj) or getattr(obj, "__module__", own) != own:
				continue
			if _requires_arguments(obj):
				self.broken.append((f"{own}.{name}", "a test function must take no arguments"))
				continue
			self.plain.append((f"{own}.{name}", obj))
		for name in sorted(dir(self.mod)):
			obj = getattr(self.mod, name, None)
			if not isinstance(obj, type):
				continue
			if not (issubclass(obj, TestCase) or issubclass(obj, unittest.TestCase)):
				continue
			if getattr(obj, "__module__", own) != own:
				continue
			for method in _test_methods(obj):
				if issubclass(obj, unittest.TestCase):
					self.unittest_cases.append((f"{own}.{obj.__name__}.{method}", obj, method))
				else:
					self.xtest_cases.append((f"{own}.{obj.__name__}.{method}", obj, method))

	def run(self):
		"""The outcomes of this group's tests, in order."""
		out = []
		for label, message in self.broken:
			out.append(("fail", label, message))
		for label, fn in self.plain:
			out.append(self._run_function(label, fn))
		for label, cls, method in self.xtest_cases:
			out.append(self._run_xtest_case(label, cls, method))
		if self.unittest_cases:
			out.extend(self._run_unittest())
		return out

	def _run_function(self, label, fn):
		try:
			fn()
		except Exception:
			return ("fail", label, traceback.format_exc())
		return ("pass", label, None)

	def _run_xtest_case(self, label, cls, method):
		instance = cls()
		try:
			instance.setUp()
			getattr(instance, method)()
		except Exception:
			return ("fail", label, traceback.format_exc())
		finally:
			try:
				instance.tearDown()
			except Exception:
				pass
		return ("pass", label, None)

	def _run_unittest(self):
		"""The `unittest.TestCase` classes of this module, through unittest.

		Unittest owns the machinery — `setUpModule`, `addCleanup`, `subTest`,
		the skip decorators — because a second version of it would be a worse
		version of it. The module has to be in `sys.modules` for unittest to
		find its fixtures, which is why the loader registers it.
		"""
		suite = unittest.TestSuite()
		for label, cls, method in self.unittest_cases:
			suite.addTest(cls(method))
		result = _Outcome()
		suite.run(result)
		return result.outcomes

def _load_file(path):
	"""Load a test file as a module and register it in `sys.modules`.

	Unittest finds a module's fixtures through `sys.modules`, so a module that
	is not registered silently loses its `setUpModule` — and the tests that
	depend on it fail for a reason that has nothing to do with them.

	The file's own directory goes on `sys.path` for the load, so a test file
	can import its neighbours by name, and xtest's own directory stays there
	afterwards, so `import xtest` works without the test file having to know
	where xtest lives.
	"""
	full = os.path.abspath(path)
	directory = os.path.dirname(full)
	name = os.path.basename(full)[:-3]
	spec = importlib.util.spec_from_file_location(name, full)
	mod = importlib.util.module_from_spec(spec)
	here = os.path.dirname(os.path.abspath(__file__))
	for entry in (here, directory):
		if entry not in sys.path:
			sys.path.insert(0, entry)
	sys.modules["xtest"] = sys.modules[__name__]
	sys.modules[name] = mod
	try:
		spec.loader.exec_module(mod)
	except BaseException:
		sys.modules.pop(name, None)
		raise
	finally:
		if directory in sys.path:
			sys.path.remove(directory)
	return mod

def _files_for(target):
	"""The test files a target names: one file, or every `test_*.py` in a
	directory."""
	path = str(target)
	if os.path.isdir(path):
		return [os.path.join(path, name) for name in sorted(os.listdir(path))
			if name.startswith("test_") and name.endswith(".py")]
	if os.path.isfile(path):
		return [path]
	raise ValueError(f"invalid target: {target!r}")

def _groups_for(target):
	"""The groups in `target`."""
	targets = target if isinstance(target, (list, tuple)) else [target]
	groups = []
	for one in targets:
		for path in _files_for(one):
			before = len(_registry)
			mod = _load_file(path)
			group = _Group(path, mod)
			# A file may register tests by decorating them, and a decorated
			# function need not be named `test_*` — the decorator is the
			# statement of intent. The registry is global, so the ones this
			# file added are the ones it added.
			for fn in _registry[before:]:
				group.plain.append((f"{fn.__module__}.{fn.__name__}", fn))
			groups.append(group)
	return groups

def run(target=None, verbose = False):
	"""Run the tests in `target` and return 0 if all passed, 1 if any failed.

	`target` may be None (the functions registered with `@test`), a file, a
	directory, or a list of files and directories. `verbose` prints each
	failure's traceback under its line; without it a failure prints its last
	line only.
	"""
	if target is None:
		groups = []
		group = _Group("<registry>", _RegistryModule())
		for fn in list(_registry):
			group.plain.append((f"{fn.__module__}.{fn.__name__}", fn))
		groups.append(group)
	else:
		groups = _groups_for(target)
	passed = failed = skipped = 0
	for group in groups:
		for outcome, label, detail in group.run():
			if outcome == "pass":
				passed += 1
				print(f"pass {label}")
			elif outcome == "skip":
				skipped += 1
				print(f"skip {label}")
			else:
				failed += 1
				print(f"FAIL {label}: {_last_line(detail)}")
				if verbose:
					print(detail)
		# The module has been run; let the next file of the same name have
		# the name without the previous one still answering for it.
		sys.modules.pop(group.mod.__name__, None)
	summary = f"{passed} passed, {failed} failed"
	if skipped:
		summary += f", {skipped} skipped"
	print(summary)
	if failed:
		return 1
	return 0

class _RegistryModule:
	"""A stand-in module for the registry, which has no file of its own."""
	__name__ = "<registry>"

def _last_line(text):
	"""The last line of a traceback: the exception and its message."""
	lines = [line for line in (text or "").splitlines() if line.strip()]
	return lines[-1] if lines else "failed"

def main(argv=None):
	"""Run the targets named on the command line."""
	import argparse
	parser = argparse.ArgumentParser(prog = "xtest", description = "Run test suites.")
	parser.add_argument("targets", nargs = "*", help = "files or directories to run")
	parser.add_argument("-v", "--verbose", action = "store_true", help = "print each failure's traceback")
	args = parser.parse_args(argv)
	return run(args.targets or None, args.verbose)

if __name__ == "__main__":
	sys.modules["xtest"] = sys.modules["__main__"]
	sys.exit(main())
