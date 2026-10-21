"""The bundler on a project it was not written against.

Every test here builds a throwaway source tree, runs `main` over it, and
asserts on the bundle that comes out. The tree is small on purpose: what is
being pinned is the shape of the bundle, not the bundler's coverage of python.

**The cases here are the ones the Space-Traveller acceptance run found.** They
are written as separate tests because each one is a separate mistake, and a
bundle that compiles is not a bundle that runs — three of these produced a
bundle that parsed and compiled clean and then raised at the first call.

**The file under test is never the entry.** The root's own prefix is empty
(D3), so nothing in it is renamed, and a case about renaming cannot show
itself there. Every tree below puts the code in a module the bundler renames
and reaches it from the root.
"""
import io,os,shutil,sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))
import xtest
from tools.pybundle.bundler import main

def _bundle(files, entry = "main.py"):
	"""The bundle of a throwaway tree, as text."""
	root = Path(tempfile.mkdtemp(prefix = "pybundle-test-"))
	try:
		for name, text in files.items():
			path = root / name
			path.parent.mkdir(parents = True, exist_ok = True)
			path.write_text(text, encoding = "utf-8", newline = "")
		sink = io.StringIO()
		main(str(root / entry), sink)
		return sink.getvalue()
	finally:
		shutil.rmtree(root, ignore_errors = True)

def _run(files, entry = "main.py", call = "run"):
	"""The bundle of a throwaway tree, run, and what it returned."""
	bundle = _bundle(files, entry)
	space = {}
	exec(compile(bundle, "<bundle>", "exec"), space)
	return space[call]()

def test_a_parameter_that_shadows_a_global_is_not_renamed():
	# The parameter is the function's own, and the body keeps it too — so the
	# bundle runs where a renamed parameter would raise a NameError.
	value = _run({
		"main.py": "import helper\n\ndef run():\n\treturn helper.compute(1)\n",
		"helper.py": "VALUE = 42\n\ndef compute(VALUE):\n\treturn VALUE + 1\n",
	})
	xtest.equal(value, 2)

def test_a_default_value_is_read_where_the_def_is():
	# A default is read in the scope around the def, so it is the module's name.
	bundle = _bundle({
		"main.py": "import helper\n\ndef run():\n\treturn helper.compute()\n",
		"helper.py": "VALUE = 42\n\ndef compute(VALUE = VALUE):\n\treturn VALUE\n",
	})
	xtest.contains("def helper__compute(VALUE = helper__VALUE)", bundle)

def test_a_name_after_a_dot_is_not_renamed():
	# `other.classes` is the module's own name — the file's `classes` is a
	# different name that happens to be spelled the same.
	bundle = _bundle({
		"main.py": "import helper\n\ndef run():\n\treturn helper.check()\n",
		"helper.py": "import other\n\nclasses = other.classes\n\ndef check():\n\treturn classes\n",
		"other.py": "classes = {}\n",
	})
	xtest.contains("helper__classes = other__classes\n", bundle)

def test_a_name_assigned_in_a_block_is_the_function_s_own():
	# Python binds a name in the function that holds the assignment, not in the
	# block the assignment sits in — so the use above the block is that local
	# and not the module's.
	bundle = _bundle({
		"main.py": "import helper\n\ndef run():\n\treturn helper.compute(True)\n",
		"helper.py": "value = 0\n\ndef compute(flag):\n\tif flag:\n\t\tvalue = 1\n\telse:\n"
			"\t\tvalue = 2\n\treturn value\n",
	})
	xtest.contains("\treturn value\n", bundle)

def test_a_class_body_s_names_are_not_visible_in_its_methods():
	# A class body is not an enclosing scope for the methods defined in it, so
	# the method reads the module's name and not the class's.
	bundle = _bundle({
		"main.py": "import helper\n\ndef run():\n\treturn helper.Items().size()\n",
		"helper.py": "def size(item):\n\treturn 1\n\nclass Items:\n\tdef size(self):\n"
			"\t\treturn size(1)\n",
	})
	xtest.contains("return helper__size(1)", bundle)

def test_a_removed_last_import_leaves_no_double_blank_line():
	# D32's third rule: removing a statement must not leave a blank pair.
	bundle = _bundle({
		"main.py": "value = 1\n\nimport helper\n",
		"helper.py": "x = 1\n",
	})
	xtest.not_equal("\n\n\n" in bundle, True)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
