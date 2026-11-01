"""Tests for xlint.py — the checks, not the CLI.

Run with: python3 dev/xtest/xtest.py tools/xlint/test/test_xlint_imports.py

xlint had no test file at all until DDRBHD5, and the gap was not cosmetic:
`check_imports` could demand a merge that cannot be written, and nothing noticed,
because a rule that is wrong on every input it ever saw looks exactly like a rule
that is right. The unsatisfiable input below is the case that pinned it.

The checks take a list of lines (without newlines, as `str.splitlines` gives them)
and return `(line_number, message)` pairs, so a test is a list in and a verdict out.
No file is written and no process is started, which is what keeps these fast enough
to run on every edit.
"""

import sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	"""The messages alone, so a test asserts on what is reported and not on its order."""
	return sorted(item[-1] for item in problems)

# --- TestPlainImports ---

"""Plain imports are comma-joined; dotted and aliased names each get their own line."""

def test_consecutive_plain_imports_are_reported_as_unmerged():
	problems = xlint.check_imports(["import json", "import collections"])
	xtest.equal(messages(problems), ["consecutive plain imports not merged"])

def test_merged_plain_imports_are_clean():
	xtest.equal(xlint.check_imports(["import json,collections"]), [])

def test_an_aliased_import_is_not_reported_as_unmerged():
	problems = xlint.check_imports(["import json", "import math as m"])
	xtest.equal(problems, [])

def test_a_plain_import_after_an_aliased_one_is_clean():
	problems = xlint.check_imports(["import math as m", "import collections"])
	xtest.equal(problems, [])

def test_an_aliased_import_does_not_propagate_to_the_next_line():
	# The input DDRBHD5 is about: with the old classifier, lines 2 and 3 were both
	# reported and no rewrite made the file clean. The alias breaks the plain run,
	# so only the genuine pair before it survives.
	problems = xlint.check_imports(["import json", "import collections", "import math as m"])
	xtest.equal(messages(problems), ["consecutive plain imports not merged"])

def test_an_aliased_import_between_two_plain_ones_breaks_the_run():
	problems = xlint.check_imports(["import json", "import math as m", "import collections"])
	xtest.equal(problems, [])

def test_an_aliased_dotted_import_is_clean():
	xtest.equal(xlint.check_imports(["import json", "import a.b as c"]), [])

def test_an_alias_sharing_a_line_with_other_names_is_reported():
	problems = xlint.check_imports(["import json,math as m"])
	xtest.equal(messages(problems), ["aliased import on a shared line"])

# --- TestFromImports ---

"""Names from one module are comma-joined; the module's own name carries the check."""

def test_two_imports_from_the_same_module_are_reported():
	problems = xlint.check_imports(["from util import ping", "from util import connect"])
	xtest.equal(messages(problems), ["same module imported on separate lines"])

def test_merged_names_from_one_module_are_clean():
	xtest.equal(xlint.check_imports(["from util import connect,ping"]), [])

def test_a_space_after_a_comma_is_reported():
	problems = xlint.check_imports(["from util import connect, ping"])
	xtest.equal(messages(problems), ["space after comma in import"])

def test_a_wildcard_import_is_reported():
	xtest.equal(messages(xlint.check_imports(["from util import *"])), ["wildcard import"])

# --- TestImportBlocks ---

"""The block-level rules: one statement per line, no blank line inside the block."""

def test_a_blank_line_between_imports_is_reported():
	problems = xlint.check_imports(["import json", "", "import collections"])
	xtest.equal(messages(problems), ["blank line between imports"])

def test_two_statements_on_one_line_are_reported():
	problems = xlint.check_imports(["import json; import collections"])
	xtest.equal(messages(problems), ["multiple statements on one line"])

def test_a_dotted_name_is_clean_beside_a_plain_one():
	xtest.equal(xlint.check_imports(["import json", "import os.path"]), [])
