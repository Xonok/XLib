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

def test_a_removed_last_import_leaves_no_double_blank_line():
	# D32's third rule: removing a statement must not leave a blank pair.
	bundle = _bundle({
		"main.py": "value = 1\n\nimport helper\n",
		"helper.py": "x = 1\n",
	})
	xtest.not_equal("\n\n\n" in bundle, True)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
