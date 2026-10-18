#!/usr/bin/env python3
"""
Tests for the bundler as a whole — R1, R2, R3, R4, R5, R7, D1, D2, D6, D8, D11,
D14, D15, D17, D21, D23, D24 and the errors.

Run with: python3 -m unittest tools.pybundle.test.test_bundler -v

Every test here runs `main` over a throwaway source tree and asserts on the
bundle it writes. `main(entry_path, out)` is that seam because D12's call graph
fixes both arguments and R5 fixes the sink. The leaves are tested directly where
their shapes are settled — `renamed` and `translate` in `test_bundler_names.py`,
`statements` in `test_bundler_source.py`, and the command line in
`test_bundler_cli.py`.

D20's rebinds are driven through `main` rather than against `translate`, because
D8 fixes what `imports` returns without naming the fields, so a `resolved` value
cannot be written down without inventing them. That is also why nothing here
asserts on the text of `imports`' own output.

**D20 reversed D9, so the import-shape tests are new rather than edited.** D9's
mechanism — a use rewritten to point straight at the callee's prefixed global —
is withdrawn; every import now emits a rebind and a use is reached through the
importing file's own name. The old class `TestNameImportsD9` asserted the
withdrawn mechanism and is replaced by the three classes below it.
"""

import contextlib,io,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pybundle.bundler import inline,main

def _start_comments(text):
	"""The start comments of a bundle, in order — one per inlined file."""
	return [line for line in text.splitlines() if line.startswith("## ")]

class BundleTestCase(unittest.TestCase):
	"""A throwaway folder per test, and one call to run `main` over a source tree."""

	def setUp(self):
		tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(tmpdir.cleanup)
		self.root = Path(tmpdir.name)

	def write_files(self, files, root=None):
		for name, text in files.items():
			path = (self.root if root is None else root) / name
			path.parent.mkdir(parents=True, exist_ok=True)
			# newline="" so a fixture writes the bytes it says, on any platform.
			path.write_text(text, encoding="utf-8", newline="")

	def bundle(self, files, entry="server.py", out=None, root=None):
		"""Runs `main` over a tree of files and returns the sink it wrote into."""
		self.write_files(files, root=root)
		sink = io.StringIO() if out is None else out
		main(str((self.root if root is None else root) / entry), sink)
		return sink

	def bundle_and_stderr(self, files, entry="server.py", root=None):
		"""The bundle and whatever reached stderr, in that order. D14 puts every
		diagnostic on stderr, so a test that wants one captures it there."""
		sink = io.StringIO()
		stderr = io.StringIO()
		with contextlib.redirect_stderr(stderr):
			self.bundle(files, entry=entry, out=sink, root=root)
		return sink.getvalue(), stderr.getvalue()

	def run_bundle(self, files, entry="server.py", root=None):
		"""The names a finished bundle holds, by running it.

		D20 is the one requirement whose emitted text cannot be read on its own: a
		rebind and a rewritten use that disagree with each other look exactly like a
		correct pair written down. These three cases are the ones the spec verified
		against real python, and running the bundle is how that is checked here.
		"""
		sink = self.bundle(files, entry=entry, root=root)
		namespace = {}
		exec(compile(sink.getvalue(), "<bundle>", "exec"), namespace)
		return namespace

class TestInliningR1(BundleTestCase):
	"""R1: a local module is inlined, and nothing else is."""

	def test_module_in_the_root_folder_is_inlined(self):
		sink = self.bundle({"server.py": "import helper\n", "helper.py": "count = 1\n"})
		self.assertIn("helper__count = 1", sink.getvalue())

	def test_module_in_a_subfolder_is_inlined(self):
		sink = self.bundle({"server.py": "import sub.helper\n", "sub/helper.py": "count = 1\n"})
		self.assertIn("sub__helper__count = 1", sink.getvalue())

	def test_file_outside_the_root_folder_is_not_inlined(self):
		sink = self.bundle({"pkg/server.py": "import helper\n", "helper.py": "count = 1\n"}, entry="pkg/server.py")
		self.assertNotIn("helper__count = 1", sink.getvalue())

	def test_file_outside_the_root_folder_is_left_as_a_normal_import(self):
		sink = self.bundle({"pkg/server.py": "import helper\n", "helper.py": "count = 1\n"}, entry="pkg/server.py")
		self.assertIn("import helper", sink.getvalue())

	def test_a_local_file_shadows_a_standard_library_name(self):
		# R1.2 is about location, not about what the name usually means.
		sink = self.bundle({"server.py": "import json\n", "json.py": "dumps = 1\n"})
		self.assertIn("json__dumps = 1", sink.getvalue())

	def test_imported_code_is_written_before_the_importing_file(self):
		# R1.4
		blocks = _start_comments(self.bundle({
			"server.py": "import helper\n",
			"helper.py": "count = 1\n",
		}).getvalue())
		self.assertEqual(blocks, ["## helper.py", "## server.py"])

	def test_non_local_import_stays_between_its_own_neighbours(self):
		# R1.5
		text = self.bundle({"server.py": "first = 1\nimport os\nsecond = 2\n"}).getvalue()
		self.assertTrue(text.index("first = 1") < text.index("import os") < text.index("second = 2"))

	def test_indented_local_import_is_inlined_even_under_a_false_condition(self):
		# Edge cases, conditional imports.
		blocks = _start_comments(self.bundle({
			"server.py": "if False: import helper\n",
			"helper.py": "count = 1\n",
		}).getvalue())
		self.assertEqual(blocks, ["## helper.py", "## server.py"])

	def test_indented_local_import_leaves_a_pass_where_it_was(self):
		# D22's `pass` clause, which settles what F18 left open: the import is
		# removed and the one-line compound body keeps its statement.
		text = self.bundle({"server.py": "if False:\n\timport helper\n", "helper.py": "count = 1\n"}).getvalue()
		self.assertIn("\tpass", text)

	def test_indented_non_local_import_stays_indented(self):
		# R1.5 — the hoisting in the edge cases applies to what gets inlined.
		text = self.bundle({"server.py": "if False:\n\timport os\n"}).getvalue()
		self.assertIn("\timport os", text)

	def test_second_reference_to_a_module_is_dropped(self):
		# R1.6
		text = self.bundle({
			"server.py": "import first\nimport shared\n",
			"first.py": "import shared\n",
			"shared.py": "count = 1\n",
		}).getvalue()
		self.assertEqual(text.count("## shared.py"), 1)

	def test_a_dropped_import_leaves_nothing_behind(self):
		text = self.bundle({
			"server.py": "import first\nimport shared\n",
			"first.py": "import shared\n",
			"shared.py": "count = 1\n",
		}).getvalue()
		self.assertNotIn("import shared", text)

	def test_circular_import_raises_nothing(self):
		# Edge cases, circular imports.
		blocks = _start_comments(self.bundle({
			"server.py": "import a\n",
			"a.py": "import b\n",
			"b.py": "import a\n",
		}).getvalue())
		self.assertEqual(blocks, ["## b.py", "## a.py", "## server.py"])

	def test_module_importing_the_root_emits_the_root_once_and_last(self):
		# R1.7
		blocks = _start_comments(self.bundle({
			"server.py": "import helper\n",
			"helper.py": "import server\n",
		}).getvalue())
		self.assertEqual(blocks, ["## helper.py", "## server.py"])

class TestOutputCommentsR2(BundleTestCase):
	"""R2: each block is delimited by a start comment and an end comment."""

	def test_a_file_one_folder_down_carries_a_leading_slash(self):
		# Q12 — a directory component carries a leading `/`, a file in the root
		# folder carries none.
		blocks = _start_comments(self.bundle({
			"server.py": "import sub.helper\n",
			"sub/helper.py": "count = 1\n",
		}).getvalue())
		self.assertEqual(blocks, ["## /sub/helper.py", "## server.py"])

	def test_end_comment_is_the_start_comment_with_a_bang(self):
		text = self.bundle({"server.py": "import sub.helper\n", "sub/helper.py": "count = 1\n"}).getvalue()
		self.assertIn("##! /sub/helper.py", text)

	def test_the_root_file_gets_the_same_comment_pair_as_everything_else(self):
		text = self.bundle({"server.py": "count = 1\n"}).getvalue()
		self.assertIn("##! server.py", text)

	def test_init_file_contributes_its_own_name_as_a_path_component(self):
		# D6, Q7 — no special case for `__init__.py`.
		blocks = _start_comments(self.bundle({
			"server.py": "import sub\n",
			"sub/__init__.py": "count = 1\n",
		}).getvalue())
		self.assertEqual(blocks, ["## /sub/__init__.py", "## server.py"])

	def test_init_file_globals_are_prefixed_with_its_own_component(self):
		text = self.bundle({"server.py": "import sub\n", "sub/__init__.py": "count = 1\n"}).getvalue()
		self.assertIn("sub____init__count = 1", text)

class TestTranslationR3(BundleTestCase):
	"""R3: globals are prefixed, the root's own definitions are not."""

	def test_module_global_is_prefixed_with_the_file_prefix(self):
		text = self.bundle({
			"server.py": "import helper\n",
			"helper.py": "def run():\n\treturn 1\n",
		}).getvalue()
		self.assertIn("def helper__run():", text)

	def test_a_reference_through_a_module_name_becomes_the_prefixed_global(self):
		text = self.bundle({
			"server.py": "import helper\nvalue = helper.run\n",
			"helper.py": "def run():\n\treturn 1\n",
		}).getvalue()
		self.assertIn("value = helper__run", text)

	def test_a_relative_import_reference_uses_the_full_modpath_prefix(self):
		# R3's worked example: `from . import api` in py/command/map.py, where a
		# reference to `api.run()` becomes `py__command__api__run()`.
		text = self.bundle({
			"server.py": "import py.command.map\n",
			"py/command/map.py": "from . import api\nvalue = api.run\n",
			"py/command/api.py": "def run():\n\treturn 1\n",
		}).getvalue()
		self.assertIn("value = py__command__api__run", text)

	def test_root_own_definitions_are_not_translated(self):
		text = self.bundle({"server.py": "def run():\n\treturn 1\n"}).getvalue()
		self.assertIn("def run():", text)

	def test_a_sibling_in_the_root_folder_is_translated_even_beside_the_root(self):
		# R3 and D3 — the exception is per file identity, not per location.
		text = self.bundle({
			"server.py": "import helper\n",
			"helper.py": "def run():\n\treturn 1\n",
		}).getvalue()
		self.assertIn("def helper__run():", text)

	def test_private_global_keeps_its_underscores_in_front_of_the_prefix(self):
		text = self.bundle({"server.py": "import helper\n", "helper.py": "_count = 1\n"}).getvalue()
		self.assertIn("_helper__count = 1", text)

	def test_an_aliased_import_reaches_the_same_renamed_global(self):
		# D6 — `y.count` and `x.count` land in the same place.
		text = self.bundle({
			"server.py": "import helper as h\nvalue = h.run\n",
			"helper.py": "def run():\n\treturn 1\n",
		}).getvalue()
		self.assertIn("value = helper__run", text)

class TestScopeR4(BundleTestCase):
	"""R4 and D2: a name bound inside a block blocks translation within it.

	Every file here is a non-root file, because the root's own names are never
	translated (R3) and a test against the root could not fail.
	"""

	TREE = {
		"server.py": "import helper\nvalue = helper.run\n",
		"helper.py": "count = 1\ndef run():\n\tpass\n",
	}

	def bundle_with(self, body):
		files = dict(self.TREE)
		files["helper.py"] = "count = 1\n" + body
		return self.bundle(files).getvalue()

	def test_function_local_assignment_blocks_the_rename(self):
		text = self.bundle_with("def run():\n\tcount = 2\n\treturn count\n")
		self.assertNotIn("return helper__count", text)

	def test_function_parameter_blocks_the_rename(self):
		text = self.bundle_with("def run(count):\n\treturn count\n")
		self.assertNotIn("return helper__count", text)

	def test_augmented_assignment_blocks_the_rename(self):
		text = self.bundle_with("def run():\n\tcount += 1\n")
		self.assertNotIn("helper__count += 1", text)

	def test_annotated_assignment_blocks_the_rename(self):
		text = self.bundle_with("def run():\n\tcount: int = 1\n")
		self.assertNotIn("helper__count: int", text)

	def test_for_target_blocks_the_rename(self):
		text = self.bundle_with("def run(items):\n\tfor count in items:\n\t\tpass\n")
		self.assertNotIn("for helper__count", text)

	def test_with_as_target_blocks_the_rename(self):
		text = self.bundle_with("def run():\n\twith open('f') as count:\n\t\tpass\n")
		self.assertNotIn("as helper__count", text)

	def test_except_as_target_blocks_the_rename(self):
		text = self.bundle_with("def run():\n\ttry:\n\t\tpass\n\texcept Exception as count:\n\t\tpass\n")
		self.assertNotIn("as helper__count", text)

	def test_walrus_target_blocks_the_rename(self):
		text = self.bundle_with("def run():\n\tif (count := 1) > 0:\n\t\tpass\n")
		self.assertNotIn("helper__count := 1", text)

	def test_nested_function_inherits_the_outer_block(self):
		# D2 — nested blocks stack.
		text = self.bundle_with("def outer():\n\tcount = 2\n\tdef inner():\n\t\treturn count\n")
		self.assertNotIn("return helper__count", text)

	def test_class_body_name_blocks_the_rename(self):
		# Q17 — a class body follows the same rule as a function.
		text = self.bundle_with("class Box:\n\tcount = 2\n")
		self.assertNotIn("helper__count = 2", text)

	def test_class_name_is_translated_as_a_module_global(self):
		text = self.bundle_with("class Box:\n\tcount = 2\n")
		self.assertIn("class helper__Box:", text)

	def test_global_name_is_translated_with_the_file_prefix(self):
		# R4 — a `global` name refers to module level, so it renames and does not
		# block a rename.
		text = self.bundle_with("def run():\n\tglobal count\n\tcount = 2\n")
		self.assertIn("helper__count = 2", text)

	def test_global_statement_names_are_translated_too(self):
		text = self.bundle_with("def run():\n\tglobal count\n\tcount = 2\n")
		self.assertIn("global helper__count", text)

	def test_nonlocal_name_is_neither_translated_nor_blocked(self):
		# R4 — a `nonlocal` name belongs to an enclosing function.
		text = self.bundle_with("def outer():\n\tcount = 2\n\tdef inner():\n\t\tnonlocal count\n\t\treturn count\n")
		self.assertNotIn("return helper__count", text)

class TestStatementsNotLinesD1(BundleTestCase):
	"""D1: a statement is a logical line, not a physical one."""

	def test_dict_continuation_lines_do_not_bind_names_in_the_function(self):
		text = self.bundle({
			"server.py": "import helper\nvalue = helper.run\n",
			"helper.py": "count = 1\ndef run():\n\tcfg = {\n\t\t\"count\": 2,\n\t}\n\treturn count\n",
		}).getvalue()
		self.assertIn("return helper__count", text)

	def test_a_multiline_string_containing_a_def_does_not_open_a_block(self):
		text = self.bundle({
			"server.py": "import helper\nvalue = helper.run\n",
			"helper.py": "count = 1\ndef run():\n\tdoc = \"\"\"\n\tdef count():\n\t\tpass\n\t\"\"\"\n\treturn count\n",
		}).getvalue()
		self.assertIn("return helper__count", text)

	def test_crlf_source_is_bundled_and_translated(self):
		# style/common.md — a library that reads lines needs a CRLF fixture.
		text = self.bundle({
			"server.py": "import helper\r\nvalue = helper.run\r\n",
			"helper.py": "count = 1\r\ndef run():\r\n\treturn count\r\n",
		}).getvalue()
		self.assertIn("value = helper__run", text)

class TestBlocksTrackedByTokensD21(BundleTestCase):
	"""D21: a block is closed by a DEDENT token, not by an indent string that
	sorts below its opener.

	`indent` is a string (D22), and in python `'\\t' < '    '` is True. The fixture
	is the one shape where the two readings disagree on source python accepts: a
	tab-indented block opened at column 8 contains a line opened at column 12 with
	`\\t    ` and closed at column 16 with `\\t        `, and the next statement
	returns to `\\t` at column 8. The tokenizer dedents to the function's body;
	comparing strings empties the stack and calls it module scope.

	Both assertions would fail on a string comparison, and neither can be reached
	from a tab body directly under a space opener — python's own tokenizer raises
	TabError on that input before block tracking is asked anything.
	"""

	TREE = {
		"server.py": "import helper\nvalue = helper.outer\n",
		"helper.py": "count = 1\ndef outer():\n\tif True:\n\t    def inner():\n\t        return 0\n\t    pass\n\tvalue = 1\n\treturn value\n",
	}

	def test_a_binding_under_a_dedented_block_stays_inside_its_function(self):
		text, _ = self.bundle_and_stderr(self.TREE)
		self.assertIn("\tvalue = 1", text)

	def test_a_name_bound_by_that_binding_is_not_read_as_the_module_global(self):
		text, _ = self.bundle_and_stderr(self.TREE)
		self.assertNotIn("return helper__value", text)

class TestOutputDestinationR5(BundleTestCase):
	"""R5: the sink is anything file-like, and the bytes are the same either way."""

	TREE = {"server.py": "import helper\nvalue = helper.run\n", "helper.py": "def run():\n\treturn 1\n"}

	def test_a_file_sink_produces_the_same_bytes_as_a_buffer(self):
		buffer_text = self.bundle(self.TREE).getvalue()
		out_path = self.root / "bundle.py"
		with open(out_path, "w", encoding="utf-8") as out:
			self.bundle(self.TREE, out=out)
		self.assertEqual(out_path.read_text(encoding="utf-8"), buffer_text)

	def test_a_real_pipe_produces_the_same_bytes_as_a_buffer(self):
		# YEBP3QB — a real pipe, not a stand-in for one.
		buffer_text = self.bundle(self.TREE).getvalue()
		read_fd, write_fd = os.pipe()
		with open(write_fd, "w", encoding="utf-8") as out:
			self.bundle(self.TREE, out=out)
		with open(read_fd, encoding="utf-8") as reader:
			pipe_text = reader.read()
		self.assertEqual(pipe_text, buffer_text)

	def test_a_buffer_the_bundler_was_given_is_not_closed(self):
		out = io.StringIO()
		self.bundle({"server.py": "count = 1\n"}, out=out)
		self.assertFalse(out.closed)

	def test_a_file_the_bundler_was_given_is_not_closed(self):
		out_path = self.root / "bundle.py"
		with open(out_path, "w", encoding="utf-8") as out:
			self.bundle({"server.py": "count = 1\n"}, out=out)
			self.assertFalse(out.closed)

	def test_a_failure_raises_the_same_error_against_a_buffer_and_against_a_file(self):
		# R5 — "The output is identical byte for byte whichever sink is used, and
		# the run does the same work and raises the same errors either way." The
		# byte half is covered above; this is the other half, and it is the half
		# a sink-conditional implementation would get wrong silently.
		files = {"server.py": "from . import gone\n"}
		with self.assertRaises(Exception) as from_buffer:
			self.bundle(dict(files), out=io.StringIO())
		out_path = self.root / "bundle.py"
		with open(out_path, "w", encoding="utf-8") as out:
			with self.assertRaises(Exception) as from_file:
				self.bundle(dict(files), out=out)
		self.assertEqual(str(from_buffer.exception), str(from_file.exception))

	def test_a_run_after_another_matches_the_same_run_alone(self):
		# R6.2 — state is piped, so nothing carries over between runs.
		alone_root = Path(tempfile.mkdtemp(prefix="pybundle_alone_"))
		self.addCleanup(shutil.rmtree, alone_root, ignore_errors=True)
		alone = self.bundle(self.TREE, root=alone_root).getvalue()
		self.bundle({"other.py": "import stranger\n", "stranger.py": "run = 1\n"}, entry="other.py")
		self.assertEqual(self.bundle(self.TREE).getvalue(), alone)

class TestInlineD11(BundleTestCase):
	"""D11 and D12: `inline(modpath, root, out, seen, entry)` is callable as the
	spec writes it, and `inline` hands back the globals it defined.

	Only root-folder files are used. A nested file's modpath would have to be
	spelled, and the spec writes a modpath dotted (R3's `py.command.api`) while
	the call graph joins it to a folder (D12) — flagged as F21 and still open.
	"""

	def test_inline_writes_the_block_for_the_file_it_is_given(self):
		sink = io.StringIO()
		self.write_files({"server.py": "count = 1\n"})
		inline("server", str(self.root), sink, {"server"}, "server")
		self.assertIn("## server.py", sink.getvalue())

	def test_inline_adds_the_modpath_to_seen(self):
		seen = set()
		self.write_files({"server.py": "count = 1\n"})
		inline("server", str(self.root), io.StringIO(), seen, "server")
		self.assertIn("server", seen)

	def test_inline_returns_the_global_names_the_file_defines(self):
		self.write_files({"server.py": "count = 1\n"})
		returned = inline("server", str(self.root), io.StringIO(), {"server"}, "server")
		self.assertIn("count", returned)

class TestErrors(BundleTestCase):
	"""The two errors the spec still lists: IMPORT_FILE_NOT_FOUND and
	RELATIVE_IMPORT_IN_ROOT. NOT_A_MODULE is retired by D15."""

	def test_relative_import_of_a_missing_module_raises(self):
		# IMPORT_FILE_NOT_FOUND — a relative import is definitely not a global.
		with self.assertRaises(Exception) as caught:
			self.bundle({"server.py": "import helper\n", "helper.py": "from . import gone\n"})
		self.assertIn("IMPORT_FILE_NOT_FOUND", str(caught.exception))

	def test_a_missing_absolute_import_is_left_in_place(self):
		# Errors — suspected globals do not raise.
		text = self.bundle({"server.py": "import definitely_not_local\n"}).getvalue()
		self.assertIn("import definitely_not_local", text)

	def test_a_relative_import_of_a_missing_module_raises_in_the_root_too(self):
		# D30 retired RELATIVE_IMPORT_IN_ROOT, so the root now reaches the check
		# every other file does: a relative import naming nothing cannot be global.
		with self.assertRaises(Exception) as caught:
			self.bundle({"server.py": "from . import gone\n"})
		self.assertIn("IMPORT_FILE_NOT_FOUND", str(caught.exception))

	def test_a_relative_import_in_the_root_file_is_not_an_error(self):
		# D30 — the ruling itself. Local targets inline, and the root's uses reach
		# their prefixed globals.
		text = self.bundle({"server.py": "from . import helper\nvalue = helper.count\n",
			"helper.py": "count = 1\n"}).getvalue()
		self.assertIn("helper__count = 1", text)
		self.assertIn("value = helper__count", text)

	def test_a_relative_import_in_a_non_root_file_does_not_raise(self):
		# D15 — the check is `modpath == entry`, so an ordinary module may still
		# use one.
		blocks = _start_comments(self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from . import api\n",
			"sub/api.py": "count = 1\n",
		}).getvalue())
		self.assertEqual(blocks, ["## /sub/api.py", "## /sub/client.py", "## server.py"])

class TestImportStatementsRemovedD8(BundleTestCase):
	"""D8: an import of an inlined module is removed from the block that had it.

	The mixed-statement cases are driven through a non-root file, because a
	non-local target is aliased under D20 and the root's empty prefix (D3) would
	make the expected text read as `import os as os`.
	"""

	def test_an_entirely_local_import_statement_is_removed(self):
		text = self.bundle({"server.py": "import helper\n", "helper.py": "count = 1\n"}).getvalue()
		self.assertNotIn("import helper", text)

	def test_a_mixed_import_statement_keeps_the_non_local_half(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import helper, os\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("import os as sub__client__os", text)

	def test_a_mixed_import_statement_loses_the_local_half(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import helper, os\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertNotIn("import helper", text)

	def test_a_mixed_statement_keeps_the_remaining_targets_in_source_order(self):
		# D32 puts each aliased target on its own line, so the order is read off
		# the bundle rather than off one comma-joined statement.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import helper, os, sys\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertLess(text.index("import os as sub__client__os"), text.index("import sys as sub__client__sys"))
		self.assertNotIn("import os as sub__client__os,", text)

	def test_a_non_local_import_statement_is_never_removed(self):
		# R1.5 — the local case above does not become a rule about every import.
		text = self.bundle({"server.py": "import os\n"}).getvalue()
		self.assertIn("import os", text)

	def test_an_indented_name_import_rebinds_at_that_indentation(self):
		# D20 with D22's `pass` clause: the statement is gone and the rebind
		# stands where it was, so the compound body keeps both of its lines.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "if False:\n\tfrom helper import count\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("\tsub__client__count = helper__count", text)

class TestNameImportsD20(BundleTestCase):
	"""D20's first two rows: a name imported into a file is that file's own
	global, and the binding is kept as a rebind rather than dissolved.

	Every non-root case uses `sub/client.py`, so the importing file's prefix is
	visible in the expected text. D24 records that a root-level rebinding comes
	out unprefixed, which is the third test pair below.
	"""

	NAME_IMPORT = {
		"server.py": "import sub.client\nvalue = sub.client.count\n",
		"sub/client.py": "from helper import count\n",
		"helper.py": "count = 1\n",
	}

	FUNCTION_SCOPE = {
		"server.py": "import sub.client\n",
		"sub/client.py": "def run():\n\tfrom helper import count\n\treturn count\n",
		"helper.py": "count = 1\n",
	}

	def test_a_local_name_import_emits_a_rebinding(self):
		text = self.bundle(self.NAME_IMPORT).getvalue()
		self.assertIn("sub__client__count = helper__count", text)

	def test_a_local_name_import_removes_its_statement(self):
		# D8 — the module was inlined, so the statement goes with it.
		text = self.bundle(self.NAME_IMPORT).getvalue()
		self.assertNotIn("from helper import", text)

	def test_a_name_imported_into_a_file_is_reached_through_that_files_own_name(self):
		# D20 — the use points at the importing file's binding, not at the
		# callee's global. D9's mechanism, which pointed at the callee's, is
		# withdrawn.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from helper import count\nvalue = count\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("value = sub__client__count", text)

	def test_the_rebinding_follows_the_block_that_defines_what_it_reads(self):
		# D20 — a rebind travels with its import, because the right-hand name may
		# not be defined yet.
		text = self.bundle(self.NAME_IMPORT).getvalue()
		self.assertTrue(text.index("##! helper.py") < text.index("sub__client__count = helper__count"))

	def test_a_local_name_import_binds_the_value_the_callee_defined(self):
		# The emitted pair works in a real python, which is the only way to tell a
		# rebind and a matching use from a rebind and a mismatched one.
		namespace = self.run_bundle(self.NAME_IMPORT)
		self.assertEqual(namespace["value"], 1)

	def test_a_rebinding_left_hand_side_is_not_prefixed_again(self):
		# D20's exemption — without it the LHS is prefixed a second time.
		text = self.bundle(self.NAME_IMPORT).getvalue()
		self.assertNotIn("sub__client__sub__client__count", text)

	def test_two_files_importing_the_same_name_both_rebind_it(self):
		# R1.6 with D20 — the second reference drops the block, and the rebind goes
		# with it only if `translate` could see `seen`, which it cannot.
		text = self.bundle({
			"server.py": "import first\nimport second\n",
			"first.py": "from shared import count\n",
			"second.py": "from shared import count\n",
			"shared.py": "count = 1\n",
		}).getvalue()
		self.assertEqual(text.count("= shared__count"), 2)

	def test_a_root_name_import_rebinds_without_a_prefix(self):
		# D24's third bullet — the root's prefix is empty (D3), so the rebind lands
		# unprefixed and has nothing else to collide with.
		text = self.bundle({
			"server.py": "from helper import count\nvalue = count\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("count = helper__count", text)

	def test_a_root_name_import_keeps_its_own_name_where_it_is_used(self):
		# The opposite of the withdrawn `test_a_root_name_import_rewrites_the_use`,
		# which asserted `value = helper__count`. With an empty prefix the rebind
		# binds the name the root already used.
		text = self.bundle({
			"server.py": "from helper import count\nvalue = count\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("value = count", text)

	def test_a_name_the_module_did_not_define_reaches_the_callees_own_import(self):
		# D20 — `Path` is helper's non-local import, so it reached helper's block
		# under helper's prefix, and the rebind reads it there.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from helper import Path\n",
			"helper.py": "from pathlib import Path\n",
		}).getvalue()
		self.assertIn("sub__client__Path = helper__Path", text)

	def test_a_non_local_name_import_is_aliased_to_the_importing_files_prefix(self):
		# D20's second row — rewritten in place, no second statement.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from pathlib import join\n",
		}).getvalue()
		self.assertIn("from pathlib import join as sub__client__join", text)

	def test_a_non_local_name_import_rewrites_its_use_to_the_alias(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from pathlib import join\nvalue = join(\"a\")\n",
		}).getvalue()
		self.assertIn("value = sub__client__join(\"a\")", text)

	def test_a_name_import_at_function_scope_rebinds_where_it_was_written(self):
		text = self.bundle(self.FUNCTION_SCOPE).getvalue()
		self.assertIn("\tsub__client__count = helper__count", text)

	def test_a_name_import_at_function_scope_rewrites_its_use_inside_the_function(self):
		text = self.bundle(self.FUNCTION_SCOPE).getvalue()
		self.assertIn("return sub__client__count", text)

	def test_a_name_import_at_function_scope_stays_function_local(self):
		# D20's verified table — the bundle gives 1 and the name is local, which
		# is the rebind-LHS exemption stated as behaviour.
		files = dict(self.FUNCTION_SCOPE, **{"server.py": "import sub.client\nvalue = sub.client.run()\n"})
		self.assertEqual(self.run_bundle(files)["value"], 1)

class TestStarImportsD20(BundleTestCase):
	"""D20: a star import of a local module gets the same answer as a name
	import — one rebind per defined global — and a star import of a non-local
	module is the one shape the alias rule cannot reach.
	"""

	STAR = {"server.py": "import sub.client\n", "sub/client.py": "from helper import *\n", "helper.py": "count = 1\n"}

	def test_a_local_star_import_removes_the_star_statement(self):
		text = self.bundle(self.STAR).getvalue()
		self.assertNotIn("import *", text)

	def test_a_local_star_import_rebinds_a_defined_global(self):
		text = self.bundle(self.STAR).getvalue()
		self.assertIn("sub__client__count = helper__count", text)

	def test_a_local_star_import_rebinds_a_defined_function(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from helper import *\n",
			"helper.py": "count = 1\ndef run():\n\tpass\n",
		}).getvalue()
		self.assertIn("sub__client__run = helper__run", text)

	def test_a_local_star_import_does_not_rebind_a_name_the_module_imported(self):
		# D20's surviving divergence — a star import carries the module's defined
		# globals only, so it does not re-export what the module imported.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from helper import *\n",
			"helper.py": "from pathlib import Path\ncount = 1\n",
		}).getvalue()
		self.assertNotIn("sub__client__Path =", text)

	def test_an_explicit_import_still_reaches_a_name_the_module_imported(self):
		# The other half of that divergence — only a star import is limited.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from helper import Path\n",
			"helper.py": "from pathlib import Path\n",
		}).getvalue()
		self.assertIn("sub__client__Path = helper__Path", text)

	def test_a_star_imported_name_is_used_through_the_importing_file(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from helper import *\nvalue = count\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("value = sub__client__count", text)

	def test_a_star_import_followed_by_a_shadowing_definition_gives_the_shadow(self):
		# D20's first verified case — the rebind is a statement, so a later
		# definition overrides it in source order. Collected at the end of the file
		# it would give 1.
		namespace = self.run_bundle({
			"server.py": "from helper import *\ncount = 2\nvalue = count\n",
			"helper.py": "count = 1\n",
		})
		self.assertEqual(namespace["value"], 2)

	def test_a_star_import_of_a_non_local_module_is_left_in_place(self):
		# D9's treatment, which D20 keeps — its bound names are not knowable, so
		# there is nothing to alias and nothing to rebind.
		text = self.bundle({"server.py": "from os import *\n"}).getvalue()
		self.assertIn("from os import *", text)

	def test_a_star_import_of_a_non_local_module_warns(self):
		# D9, and D24's one surviving collision source.
		_, stderr_text = self.bundle_and_stderr({"server.py": "from os import *\n"})
		self.assertTrue(stderr_text)

class TestNonLocalModuleImportsD20(BundleTestCase):
	"""D20's third and fifth rows: a non-local module import is aliased to the
	importing file's prefix, except where python binds a name the statement does
	not spell — which is every dotted import.
	"""

	DOTTED = {
		"server.py": "import sub.client\n",
		"sub/client.py": "import email.utils\n",
	}

	def test_a_non_local_module_import_is_aliased_to_the_importing_files_prefix(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import math\n",
		}).getvalue()
		self.assertIn("import math as sub__client__math", text)

	def test_a_use_of_a_non_local_module_import_goes_through_the_alias(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import math\nvalue = math.pi\n",
		}).getvalue()
		self.assertIn("value = sub__client__math.pi", text)

	def test_a_dotted_import_keeps_its_statement(self):
		text = self.bundle(self.DOTTED).getvalue()
		self.assertIn("import email.utils", text)

	def test_a_dotted_import_adds_a_rebind_for_the_name_python_actually_binds(self):
		text = self.bundle(self.DOTTED).getvalue()
		self.assertIn("sub__client__email = email", text)

	def test_the_dotted_rebind_follows_the_statement_that_binds_it(self):
		# Collected at the top of the block, the rebind would read `email` before
		# the statement that binds it.
		text = self.bundle(self.DOTTED).getvalue()
		self.assertTrue(text.index("import email.utils") < text.index("sub__client__email = email"))

	def test_a_use_that_reaches_past_the_leaf_goes_through_the_parent(self):
		# D20's half-silent failure — `email.utils.parseaddr` survives a naive
		# alias by coincidence, so a test written against the leaf reports green on
		# a file broken for the other use.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import email.utils\nparsed = email.utils.parseaddr(\"a\")\n",
		}).getvalue()
		self.assertIn("sub__client__email.utils.parseaddr", text)

	def test_a_use_of_the_dotted_imports_own_parent_is_reachable(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import email.utils\nmessage = email.message_from_string(\"a\")\n",
		}).getvalue()
		self.assertIn("sub__client__email.message_from_string", text)

	def test_an_aliased_dotted_import_is_aliased_rather_than_kept(self):
		# D20's condition is general, not a carve-out for dotted statements:
		# `eu` is spelled, so the alias rule applies and hands the file the leaf,
		# which is what python hands it too.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "import email.utils as eu\n",
		}).getvalue()
		self.assertIn("import email.utils as sub__client__eu", text)

class TestEmittedOutputIsLintCleanD32(BundleTestCase):
	"""D32: a bundle must be xlint-clean, and the obligation is the bunder's own
	edits — text carried verbatim from a source that is already linted is not its
	responsibility.

	**The test invokes xlint rather than being a fixture**, because `is_ignored`
	excludes any path part named `test` (`AK633QC`) — a bundle written into this
	folder would be invisible to the very check it exists to satisfy. It also
	asserts the *sources* are clean, which is the other half: a bundle cannot be
	cleaner than what it was made of, and the difference between the two is
	exactly the bundler's own work.
	"""

	TREE = {
		"server.py": "import sub.client\nimport time,sys\nimport email.utils\n"
			"\nvalue = sub.client.run() + time.time() + len(sys.argv)\n",
		"sub/client.py": "import helper,os,json\nimport email.utils\nfrom pathlib import join\n"
			"from helper import count\n"
			"\ndef run():\n\tfrom http import HTTPStatus\n"
			"\treturn join(\"a\"), HTTPStatus.OK, count, json.dumps({}), os.sep\n",
		"helper.py": "import math\ncount = 1\nvalue = math.pi\n",
	}

	def _linted(self, path):
		found = subprocess.run([sys.executable, str(ROOT / "tools" / "xlint" / "xlint.py"), str(path)],
			capture_output = True, text = True)
		return found.returncode, found.stdout.strip()

	def test_the_fixtures_themselves_are_lint_clean(self):
		for name, text in self.TREE.items():
			self.write_files({name: text})
			_, said = self._linted(self.root / name)
			self.assertEqual(said, "clean", f"{name} is not lint clean")

	def test_the_bundle_is_lint_clean(self):
		self.write_files(self.TREE)
		path = self.root / "bundle.py"
		path.write_text(self.bundle(self.TREE).getvalue(), encoding = "utf-8", newline = "")
		code, said = self._linted(path)
		self.assertEqual(said, "clean")

	def test_the_bundle_parses(self):
		# The shape the lint test cannot see: a statement emitted at the wrong
		# indentation is still perfectly valid *text*, and fails at compile.
		compile(self.bundle(self.TREE).getvalue(), "<bundle>", "exec")

	def test_an_emitted_import_carries_no_space_after_a_comma(self):
		text = self.bundle({"server.py": "import sub.client\n",
			"sub/client.py": "import os,sys\n"}).getvalue()
		self.assertNotIn(", as", text)
		self.assertNotIn("import os as sub__client__os,", text)

	def test_an_indented_non_local_name_import_keeps_its_indentation(self):
		# Found while implementing D32: the statement came out at column 0, so the
		# bundle did not parse.
		text = self.bundle({"server.py": "import sub.client\n",
			"sub/client.py": "def run():\n\tfrom pathlib import join\n\treturn join(\"a\")\n"}).getvalue()
		self.assertIn("\tfrom pathlib import join as sub__client__join", text)

	def test_a_removed_import_between_two_blanks_leaves_no_double_blank(self):
		text = self.bundle({"server.py": "\"doc\"\n\nimport helper\n\nvalue = 1\n",
			"helper.py": "count = 1\n"}).getvalue()
		self.assertNotIn("\n\n\n", text)

	def test_a_double_blank_the_source_wrote_is_carried(self):
		# The other half of D32's rule: a blank pair the bundler did not create is
		# the source's own finding, and normalising it would be the bundler
		# claiming a style the source never owed.
		text = self.bundle({"server.py": "value = 1\n\n\nother = 2\n"}).getvalue()
		self.assertIn("\n\n\n", text)

class TestNothingMovesD33(BundleTestCase):
	"""D33: where the bundled name is the name the source used, no alias and no
	rebind is written and the statement stands as written.
	"""

	def test_a_non_local_import_in_the_root_is_left_alone(self):
		text = self.bundle({"server.py": "import time,sys\n"}).getvalue()
		self.assertIn("import time,sys", text)
		self.assertNotIn("import time as time", text)

	def test_a_non_local_name_import_in_the_root_keeps_its_as_clause(self):
		# The reason the statement is taken verbatim rather than rebuilt: a
		# rebuilt one would drop the alias the source spelled and the name would
		# then be undefined.
		text = self.bundle({"server.py": "from pathlib import join as j\nvalue = j(\"a\")\n"}).getvalue()
		self.assertIn("from pathlib import join as j", text)
		self.assertNotIn("join as j as j", text)

	def test_a_dotted_import_in_the_root_adds_no_rebind(self):
		text = self.bundle({"server.py": "import email.utils\nparsed = email.utils.parseaddr(\"a\")\n"}).getvalue()
		self.assertIn("import email.utils", text)
		self.assertNotIn("email = email", text)

	def test_a_non_root_file_still_gets_its_alias_and_its_rebind(self):
		# The negative case, and the one that matters: a suite covering only the
		# root cannot tell a right comparison from aliases having stopped being
		# emitted at all.
		text = self.bundle({"server.py": "import sub.client\n",
			"sub/client.py": "import math\nvalue = math.pi\n"}).getvalue()
		self.assertIn("import math as sub__client__math", text)
		self.assertIn("value = sub__client__math.pi", text)

	def test_a_dotted_import_in_a_non_root_file_still_adds_its_rebind(self):
		text = self.bundle({"server.py": "import sub.client\n",
			"sub/client.py": "import email.utils\n"}).getvalue()
		self.assertIn("sub__client__email = email", text)

class TestDiagnosticsGoToStderrD14(BundleTestCase):
	"""D14: every diagnostic reaches stderr, and none reaches the sink."""

	TREE = {
		"server.py": "import first\nimport shared\n",
		"first.py": "import shared\n",
		"shared.py": "count = 1\n",
	}

	def test_a_dropped_second_reference_writes_a_message_to_stderr(self):
		_, stderr_text = self.bundle_and_stderr(self.TREE)
		self.assertTrue(stderr_text)

	def test_a_dropped_second_reference_writes_nothing_to_stdout(self):
		sink = io.StringIO()
		stdout = io.StringIO()
		stderr = io.StringIO()
		with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			self.bundle(self.TREE, out=sink)
		self.assertEqual(stdout.getvalue(), "")

	def test_a_file_with_no_diagnostics_writes_nothing_to_stderr(self):
		_, stderr_text = self.bundle_and_stderr({"server.py": "count = 1\n"})
		self.assertEqual(stderr_text, "")

class TestIndentationWarningD23(BundleTestCase):
	"""D23: the fourth diagnostic. It anchors on the root file, reports one entry
	per offending file, ignores what python does not care about, and never
	refuses.

	D29 settles what an entry carries — the file's path, the first offending line's
	number, and that line's text — so the three tests below no longer read a form
	the spec leaves open. F29 was what made them a guess; it is answered.
	"""

	TWO_OFFENDERS = {
		"server.py": "def run():\n    value = 1\nimport sub.client\n",
		"sub/client.py": "def run():\n\tfirst_offender = 1\n\tsecond_offender = 2\n",
	}

	def test_a_file_whose_indentation_type_differs_from_a_space_root_is_reported(self):
		# The root carries the space convention, so the file's tabs disagree with
		# the anchor. A root with nothing indented would not do: D23's fallback
		# anchor is the first file that *has* indentation, which would be this
		# very file, and it would then agree with itself.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "def run():\n    value = 1\nimport sub.client\n",
			"sub/client.py": "def run():\n\tvalue = 1\n",
		})
		self.assertTrue(stderr_text)

	def test_a_file_whose_indentation_type_differs_from_a_tab_root_is_reported(self):
		# The anchor is the root's convention, so tabs are not the wrong one.
		# The root has to carry the tab convention for that to mean anything; see
		# the test above for why a root with no indentation cannot stand in.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "def run():\n\tvalue = 1\nimport sub.client\n",
			"sub/client.py": "def run():\n    value = 1\n",
		})
		self.assertTrue(stderr_text)

	def test_a_file_whose_indentation_matches_the_root_is_not_reported(self):
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "def run():\n\tvalue = 1\nimport sub.client\n",
			"sub/client.py": "def run():\n\tvalue = 2\n",
		})
		self.assertEqual(stderr_text, "")

	def test_a_line_carrying_both_indentation_types_is_reported(self):
		# The offending file's only indented line starts with the anchor's tab and
		# goes on to carry spaces, so a first-character check would miss it.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "def run():\n\tvalue = 1\nimport sub.client\n",
			"sub/client.py": "def run():\n\t    value = 2\n",
		})
		self.assertTrue(stderr_text)

	def test_a_whitespace_only_line_of_the_other_type_is_ignored(self):
		_, stderr_text = self.bundle_and_stderr({"server.py": "def run():\n    value = 1\n\t\n"})
		self.assertEqual(stderr_text, "")

	def test_a_multiline_string_interior_of_the_other_type_is_ignored(self):
		# Every code line here is space-indented to match the root; the tab lines
		# are inside the string, which is one token.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "def run():\n    value = 1\nimport sub.client\n",
			"sub/client.py": "def run():\n    doc = \"\"\"\n\tinside = 1\n\t\"\"\"\n    return doc\n",
		})
		self.assertEqual(stderr_text, "")

	def test_a_bracket_continuation_line_of_the_other_type_is_ignored(self):
		# D1 reaches here: a statement is a logical line, so the scan sees the
		# opening `cfg = {` and its indentation, not the continuation lines under
		# it — six of which in this repo would otherwise trip the rule.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "import sub.client\n",
			"sub/client.py": "def run():\n    cfg = {\n\t\t\"a\": 1,\n\t}\n    return cfg\n",
		})
		self.assertEqual(stderr_text, "")

	def test_the_report_names_the_first_offending_line(self):
		_, stderr_text = self.bundle_and_stderr(self.TWO_OFFENDERS)
		self.assertIn("first_offender", stderr_text)

	def test_the_report_does_not_name_a_later_offending_line(self):
		_, stderr_text = self.bundle_and_stderr(self.TWO_OFFENDERS)
		self.assertNotIn("second_offender", stderr_text)

	def test_a_file_with_two_offending_lines_is_reported_once(self):
		# "One entry per offending file, naming that file's first offending line."
		_, stderr_text = self.bundle_and_stderr(self.TWO_OFFENDERS)
		self.assertEqual(stderr_text.count("first_offender"), 1)

	def test_the_report_carries_the_offending_files_path(self):
		# D29 — the path is written the way the start comments write it, so R2's
		# rule applies and the directory component carries a leading `/`.
		_, stderr_text = self.bundle_and_stderr(self.TWO_OFFENDERS)
		self.assertIn("/sub/client.py", stderr_text)

	def test_the_report_carries_the_first_offending_lines_number(self):
		# D29 — the third element. The offending line is line 12 and "12" appears
		# nowhere else in an entry: not in the path, not in the line's own text.
		# The padding is ten comment lines, which D23 ignores as non-code while
		# they still take up line numbers.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "def run():\n    value = 1\nimport sub.client\n",
			"sub/client.py": "# one\n# two\n# three\n# four\n# five\n# six\n# seven\n"
				"# eight\n# nine\n# ten\ndef run():\n\tvalue = 1\n",
		})
		self.assertIn("12", stderr_text)

	def test_a_mixed_convention_tree_is_bundled_anyway(self):
		# D23's "never refuse" — and the file that gets reported is in this bundle,
		# so the warning and the bundle are both there.
		sink, _ = self.bundle_and_stderr({
			"server.py": "import sub.client\n",
			"sub/client.py": "def run():\n\tvalue = 1\n",
		})
		self.assertIn("## server.py", sink)

	def test_a_root_without_indentation_reports_nothing_when_the_files_agree(self):
		# Nothing in the root is indented, so the convention comes from the first
		# file that is — and here the only such file agrees with the other.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "count = 1\nimport sub.client\n",
			"sub/client.py": "def run():\n\tvalue = 2\n",
		})
		self.assertEqual(stderr_text, "")

	def test_a_root_without_indentation_still_reports_files_that_disagree(self):
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "count = 1\nimport sub.client\n",
			"sub/client.py": "import sub.other\ndef run():\n\tvalue = 2\n",
			"sub/other.py": "def run():\n    value = 3\n",
		})
		self.assertTrue(stderr_text)

class TestBareModuleReferencesD17(BundleTestCase):
	"""D17: a module name used other than as an attribute base has no rewrite,
	and the bundler neither detects it nor raises."""

	def test_a_bare_module_reference_is_carried_into_the_bundle_unchanged(self):
		text = self.bundle({"server.py": "import helper\nvalue = helper\n", "helper.py": "count = 1\n"}).getvalue()
		self.assertIn("value = helper", text)

	def test_a_bare_module_reference_is_not_detected(self):
		# Detection would have raised, as it does for RELATIVE_IMPORT_IN_ROOT.
		# The shape is the one D17 names: `import helper.sub` binds the bare
		# name `helper`, and using it bare has no rewrite.
		text = self.bundle({
			"server.py": "import helper.sub\nvalue = helper\n",
			"helper/sub.py": "count = 1\n",
		}).getvalue()
		self.assertIn("value = helper", text)

class TestNameCollisionsD24(BundleTestCase):
	"""D24: three of D19's four collision sources are prevented by the alias rule
	rather than merely being unlikely, and the survivor is the non-local star
	import — pinned by `test_a_star_import_of_a_non_local_module_warns` above.
	"""

	def test_a_name_aliased_in_the_first_file_takes_that_files_prefix(self):
		text = self.bundle({
			"server.py": "import first\nimport second\n",
			"first.py": "import cmath as m\nvalue = m\n",
			"second.py": "import math as m\nvalue = m\n",
		}).getvalue()
		self.assertIn("import cmath as first__m", text)

	def test_the_same_name_aliased_in_the_second_file_takes_its_own_prefix(self):
		# D19's second source — two files binding `m`, which the alias rule turns
		# into two names that cannot meet.
		text = self.bundle({
			"server.py": "import first\nimport second\n",
			"first.py": "import cmath as m\nvalue = m\n",
			"second.py": "import math as m\nvalue = m\n",
		}).getvalue()
		self.assertIn("import math as second__m", text)

	def test_a_collision_between_two_aliased_imports_is_not_warned_about(self):
		# D24 — most collisions are now prevented, so there is less to warn about
		# rather than more, and D19's declined warning stays declined either way.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "import first\nimport second\n",
			"first.py": "import math as m\nvalue = m\n",
			"second.py": "import cmath as m\nvalue = m\n",
		})
		self.assertEqual(stderr_text, "")

	def test_a_root_level_rebinding_is_unprefixed_beside_another_files_prefix(self):
		# D24's third source — the root's rebind is the only unprefixed name the
		# bundler writes, so it has nothing to collide with.
		text = self.bundle({
			"server.py": "import sub.client\nfrom helper import count\nvalue = count\n",
			"helper.py": "count = 1\n",
			"sub/client.py": "import math\n",
		}).getvalue()
		self.assertIn("count = helper__count", text)

class TestNonNameTextSurvivesR7(BundleTestCase):
	"""R7: comments, blank lines and spacing are carried through untouched."""

	def test_a_comment_is_carried_into_the_bundle_unchanged(self):
		text = self.bundle({
			"server.py": "import helper\n# keep me\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("# keep me", text)

	def test_a_blank_line_inside_a_file_is_carried_into_the_bundle(self):
		text = self.bundle({
			"server.py": "import helper\n",
			"helper.py": "count = 1\n\nrun = 2\n",
		}).getvalue()
		self.assertIn("\n\n", text)

	def test_indentation_of_a_kept_statement_is_unchanged(self):
		text = self.bundle({"server.py": "if True:\n\tcount = 1\n"}).getvalue()
		self.assertIn("\n\tcount = 1", text)

if __name__ == "__main__":
	unittest.main()
