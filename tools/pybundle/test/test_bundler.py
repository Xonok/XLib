#!/usr/bin/env python3
"""
Tests for the bundler as a whole — R1, R2, R3, R4, R5, R7, D1, D2, D6, D8, D9,
D14, D15, D17, D19 and the errors.

Run with: python3 -m unittest tools.pybundle.test.test_bundler -v

Every test here runs `main` over a throwaway source tree and asserts on the
bundle it writes. `main(entry_path, out)` is that seam because D12's call graph
fixes both arguments and R5 fixes the sink. The leaves are tested directly where
their shapes are now settled — `renamed` and `translate` in `test_bundler_names.py`,
`statements` in `test_bundler_source.py`, and the command line in
`test_bundler_cli.py`.
"""

import contextlib,io,os,shutil,sys,tempfile,unittest
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

	def bundle_and_stderr(self, files, entry="server.py"):
		"""The bundle and whatever reached stderr, in that order. D14 puts every
		diagnostic on stderr, so a test that wants one captures it there."""
		sink = io.StringIO()
		stderr = io.StringIO()
		with contextlib.redirect_stderr(stderr):
			self.bundle(files, entry=entry, out=sink)
		return sink.getvalue(), stderr.getvalue()

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
		# Edge cases — an indented import is hoisted, so its own line goes and a
		# pass is left behind at that indentation.
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
	the call graph joins it to a folder (D12) — flagged as F21.
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

	def test_a_relative_import_in_the_root_file_raises(self):
		# RELATIVE_IMPORT_IN_ROOT — D15 puts the check in `inline`, which is the
		# only function that is handed `entry`.
		with self.assertRaises(Exception) as caught:
			self.bundle({"server.py": "from . import helper\n", "helper.py": "count = 1\n"})
		self.assertIn("RELATIVE_IMPORT_IN_ROOT", str(caught.exception))

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
	"""D8: an import of an inlined module is removed from the block that had it."""

	def test_an_entirely_local_import_statement_is_removed(self):
		text = self.bundle({"server.py": "import helper\n", "helper.py": "count = 1\n"}).getvalue()
		self.assertNotIn("import helper", text)

	def test_a_mixed_import_statement_keeps_the_non_local_half(self):
		text = self.bundle({"server.py": "import helper, os\n", "helper.py": "count = 1\n"}).getvalue()
		self.assertIn("import os", text)

	def test_a_mixed_import_statement_loses_the_local_half(self):
		text = self.bundle({"server.py": "import helper, os\n", "helper.py": "count = 1\n"}).getvalue()
		self.assertNotIn("import helper", text)

	def test_a_mixed_statement_keeps_the_remaining_targets_in_source_order(self):
		text = self.bundle({
			"server.py": "import helper, os, sys\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("import os, sys", text)

	def test_a_non_local_import_statement_is_never_removed(self):
		# R1.5 — the local case above does not become a rule about every import.
		text = self.bundle({"server.py": "import os\n"}).getvalue()
		self.assertIn("import os", text)

class TestNameImportsD9(BundleTestCase):
	"""D9, as revised: `from x import y` needs no rebinding.

	There are two cases and they end up the same. If `y` is a file it is just
	`import x.y`, and the module path does the work. If `y` is a name inside `x`,
	every use of `y` is treated as `x.y`, which is the same rewrite with the
	module path reached separately. Either way the name lands at `x__y`, prefixed
	by wherever `x` lives.
	"""

	NAME_IMPORT = {"server.py": "import sub.client\n", "sub/client.py": "from helper import count\nvalue = count\n", "helper.py": "count = 1\n"}

	def test_a_name_imported_from_a_local_module_becomes_the_prefixed_global(self):
		text = self.bundle(self.NAME_IMPORT).getvalue()
		self.assertIn("value = helper__count", text)

	def test_a_name_import_from_a_local_module_emits_no_rebinding(self):
		# One `helper__count` — the definition. A rebinding would make two.
		text = self.bundle(self.NAME_IMPORT).getvalue()
		self.assertNotIn("count = helper__count", text)

	def test_a_name_import_statement_is_removed(self):
		# D8 — the module was inlined, so the statement goes with it.
		text = self.bundle(self.NAME_IMPORT).getvalue()
		self.assertNotIn("from helper import", text)

	def test_a_from_import_of_a_module_is_the_module_path(self):
		# The other half of the two cases: `nested` is a file, so this is
		# `import helper.nested` wearing different syntax.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from helper import nested\nvalue = nested.run\n",
			"helper/nested.py": "def run():\n\treturn 1\n",
		}).getvalue()
		self.assertIn("value = helper__nested__run", text)

	def test_a_root_name_import_rewrites_the_use(self):
		text = self.bundle({
			"server.py": "from helper import count\nvalue = count\n",
			"helper.py": "count = 1\n",
		}).getvalue()
		self.assertIn("value = helper__count", text)

	def test_a_name_import_from_a_non_local_module_becomes_a_module_import(self):
		# `join` is a name in pathlib, so every use of it becomes `pathlib.join`,
		# and the statement has to be the one that binds `pathlib`.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from pathlib import join\n",
		}).getvalue()
		self.assertIn("import pathlib", text)

	def test_a_use_of_a_non_local_name_import_becomes_an_attribute_of_it(self):
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from pathlib import join\nvalue = join(\"a\")\n",
		}).getvalue()
		self.assertIn("value = pathlib.join(\"a\")", text)

	def test_a_star_import_of_a_local_module_removes_the_star_statement(self):
		text = self.bundle({"server.py": "from helper import *\n", "helper.py": "count = 1\n"}).getvalue()
		self.assertNotIn("import *", text)

	def test_a_star_import_of_a_non_local_module_is_left_in_place(self):
		# D9 — its bound names are not known, so there is nothing to rebind.
		text = self.bundle({"server.py": "from os import *\n"}).getvalue()
		self.assertIn("from os import *", text)

	def test_a_star_import_of_a_non_local_module_warns(self):
		# D9 — the warning is what keeps the known limit visible.
		_, stderr_text = self.bundle_and_stderr({"server.py": "from os import *\n"})
		self.assertTrue(stderr_text)

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

class TestNameCollisionsD19(BundleTestCase):
	"""D19: names bound by non-local imports are not prefixed, and a collision
	between two of them is neither detected nor warned about."""

	def test_a_non_local_module_import_binds_an_unprefixed_name(self):
		text = self.bundle({"server.py": "import math\nvalue = math.pi\n"}).getvalue()
		self.assertIn("value = math.pi", text)

	def test_two_files_binding_the_same_non_local_name_both_keep_it(self):
		# The case D19 names: `import cmath as m` here, `import math as m` there.
		text = self.bundle({
			"server.py": "import first\nimport second\n",
			"first.py": "import cmath as m\nvalue = m\n",
			"second.py": "import math as m\nvalue = m\n",
		}).getvalue()
		self.assertEqual(text.count("import cmath as m") + text.count("import math as m"), 2)

	def test_a_non_local_name_collision_is_not_warned_about(self):
		# D19 — a warning was considered and declined.
		_, stderr_text = self.bundle_and_stderr({
			"server.py": "import first\nimport second\n",
			"first.py": "import math as m\nvalue = m\n",
			"second.py": "import cmath as m\nvalue = m\n",
		})
		self.assertEqual(stderr_text, "")

	def test_a_name_import_from_a_non_local_module_binds_an_unprefixed_name(self):
		# D19's exception: a non-local name import is linked to the module path,
		# which is a plain dotted name with no prefix on it.
		text = self.bundle({
			"server.py": "import sub.client\n",
			"sub/client.py": "from math import pi\nvalue = pi\n",
		}).getvalue()
		self.assertIn("value = math.pi", text)

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
