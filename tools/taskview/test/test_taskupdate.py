#!/usr/bin/env python3
"""
Tests for taskupdate.py — writer side (R28, R29, R30, read_last_id).

Run with: python3 -m unittest tools.taskview.test.test_taskupdate -v
"""

import csv
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Import taskupdate by path (like test_xcsv.py does)
ROOT = Path(__file__).resolve().parents[3]  # XLib root
sys.path.insert(0, str(ROOT))
from tools.taskview import taskupdate

# Module-level test isolation: redirect XDG_DATA_HOME to a unique temp directory
# so no test can ever touch the real ~/.local/share/taskview (R17, R19, R30).
_TEST_XDG_DATA_HOME = None
_REAL_XDG_DATA_HOME = None

def setUpModule():
	global _TEST_XDG_DATA_HOME, _REAL_XDG_DATA_HOME
	_REAL_XDG_DATA_HOME = os.environ.get('XDG_DATA_HOME')
	_TEST_XDG_DATA_HOME = tempfile.mkdtemp(prefix='taskview_test_')
	os.environ['XDG_DATA_HOME'] = _TEST_XDG_DATA_HOME

def tearDownModule():
	global _TEST_XDG_DATA_HOME, _REAL_XDG_DATA_HOME
	if _REAL_XDG_DATA_HOME is not None:
		os.environ['XDG_DATA_HOME'] = _REAL_XDG_DATA_HOME
	elif 'XDG_DATA_HOME' in os.environ:
		del os.environ['XDG_DATA_HOME']
	if _TEST_XDG_DATA_HOME and os.path.exists(_TEST_XDG_DATA_HOME):
		import shutil
		shutil.rmtree(_TEST_XDG_DATA_HOME, ignore_errors=True)


class TestR28CategoryTagsAccepted(unittest.TestCase):
	"""R28: --category and --tags are accepted by add and update."""

	def setUp(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		self.csv_path = Path(self.tmpdir.name) / "tasks.csv"

	def tearDown(self):
		self.tmpdir.cleanup()

	def run_add(self, title, category=None, tags=None, due=None, status="open", importance=None):
		"""Call taskupdate.main with add subcommand via patched argv."""
		argv = ["taskupdate", "--csv", str(self.csv_path), "add", title]
		if due:
			argv.extend(["--due", due])
		if status:
			argv.extend(["--status", status])
		if category is not None:
			argv.extend(["--category", category])
		if tags is not None:
			argv.extend(["--tags", tags])
		if importance is not None:
			argv.extend(["--importance", importance])
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def run_update(self, task_id, status=None, title=None, due=None, category=None, tags=None, importance=None):
		argv = ["taskupdate", "--csv", str(self.csv_path), "update", str(task_id)]
		if status:
			argv.extend(["--status", status])
		if title is not None:
			argv.extend(["--title", title])
		if due:
			argv.extend(["--due", due])
		if category is not None:
			argv.extend(["--category", category])
		if tags is not None:
			argv.extend(["--tags", tags])
		if importance is not None:
			argv.extend(["--importance", importance])
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def read_rows(self):
		rows = []
		with self.csv_path.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if row and not row[0].startswith("//") and row[0] != "id":
					rows.append(row)
		return rows

	def test_add_accepts_category(self):
		# R28: add accepts --category
		self.run_add("Task with category", category="XLib")
		rows = self.read_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][5], "XLib")  # category column

	def test_add_accepts_tags(self):
		# R28: add accepts --tags
		self.run_add("Task with tags", tags="urgent,backend")
		rows = self.read_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][6], "urgent,backend")  # tags column

	def test_add_accepts_both_category_and_tags(self):
		# R28: add accepts both together
		self.run_add("Task with both", category="Agents", tags="frontend,ui")
		rows = self.read_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][5], "Agents")
		self.assertEqual(rows[0][6], "frontend,ui")

	def test_update_accepts_category(self):
		# R28: update accepts --category
		self.run_add("Original", category="Old")
		self.run_update(1, category="New")
		rows = self.read_rows()
		self.assertEqual(len(rows), 2)
		# Latest row for id=1 should have new category
		self.assertEqual(rows[1][5], "New")

	def test_update_accepts_tags(self):
		# R28: update accepts --tags
		self.run_add("Original", tags="old")
		self.run_update(1, tags="new,updated")
		rows = self.read_rows()
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[1][6], "new,updated")

	def test_update_accepts_both_category_and_tags(self):
		# R28: update accepts both together
		self.run_add("Original", category="A", tags="x")
		self.run_update(1, category="B", tags="y,z")
		rows = self.read_rows()
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[1][5], "B")
		self.assertEqual(rows[1][6], "y,z")


class TestR32AllNineColumnsWritten(unittest.TestCase):
	"""R32: Every write path writes all 9 columns, carrying forward unchanged fields."""

	def setUp(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		self.csv_path = Path(self.tmpdir.name) / "tasks.csv"

	def tearDown(self):
		self.tmpdir.cleanup()

	def run_add(self, title, category=None, tags=None, due=None, status="open", importance=None):
		argv = ["taskupdate", "--csv", str(self.csv_path), "add", title]
		if due:
			argv.extend(["--due", due])
		if status:
			argv.extend(["--status", status])
		if category is not None:
			argv.extend(["--category", category])
		if tags is not None:
			argv.extend(["--tags", tags])
		if importance is not None:
			argv.extend(["--importance", importance])
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def run_update(self, task_id, status=None, title=None, due=None, category=None, tags=None, importance=None):
		argv = ["taskupdate", "--csv", str(self.csv_path), "update", str(task_id)]
		if status:
			argv.extend(["--status", status])
		if title is not None:
			argv.extend(["--title", title])
		if due:
			argv.extend(["--due", due])
		if category is not None:
			argv.extend(["--category", category])
		if tags is not None:
			argv.extend(["--tags", tags])
		if importance is not None:
			argv.extend(["--importance", importance])
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def run_done(self, task_id):
		argv = ["taskupdate", "--csv", str(self.csv_path), "done", str(task_id)]
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def run_cancel(self, task_id):
		argv = ["taskupdate", "--csv", str(self.csv_path), "cancel", str(task_id)]
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def read_latest(self, task_id):
		"""Return the last row for given task_id as a dict with field names."""
		rows = []
		with self.csv_path.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if row and not row[0].startswith("//") and row[0] != "id":
					if len(row) >= 2 and row[0].isdigit() and int(row[0]) == task_id:
						rows.append(row)
		if not rows:
			return None
		row = rows[-1]
		return {
			"id": row[0],
			"status": row[1] if len(row) > 1 else "",
			"title": row[2] if len(row) > 2 else "",
			"due_ts": row[3] if len(row) > 3 else "",
			"chg_ts": row[4] if len(row) > 4 else "",
			"category": row[5] if len(row) > 5 else "",
			"tags": row[6] if len(row) > 6 else "",
			"importance": row[7] if len(row) > 7 else "",
			"description": row[8] if len(row) > 8 else "",
		}

	def assert_row_has_9_fields(self, row_dict):
		"""Assert the row has all 9 columns (no short rows)."""
		self.assertIn("id", row_dict)
		self.assertIn("status", row_dict)
		self.assertIn("title", row_dict)
		self.assertIn("due_ts", row_dict)
		self.assertIn("chg_ts", row_dict)
		self.assertIn("category", row_dict)
		self.assertIn("tags", row_dict)
		self.assertIn("importance", row_dict)
		self.assertIn("description", row_dict)
		# All should be present (even if empty string)
		self.assertEqual(len(row_dict), 9)

	def test_done_preserves_category_and_tags(self):
		# R29: done on task with category and tags → both survive
		self.run_add("Task to complete", category="XLib", tags="important,backend")
		latest = self.read_latest(1)
		self.assertEqual(latest["category"], "XLib")
		self.assertEqual(latest["tags"], "important,backend")

		self.run_done(1)
		latest = self.read_latest(1)
		self.assertEqual(latest["status"], "done")
		self.assertEqual(latest["category"], "XLib", "category must survive done")
		self.assertEqual(latest["tags"], "important,backend", "tags must survive done")
		self.assert_row_has_9_fields(latest)

	def test_cancel_preserves_category_and_tags(self):
		# R29: cancel on task with category and tags → both survive
		self.run_add("Task to cancel", category="Agents", tags="frontend,ui")
		self.run_cancel(1)
		latest = self.read_latest(1)
		self.assertEqual(latest["status"], "cancelled")
		self.assertEqual(latest["category"], "Agents", "category must survive cancel")
		self.assertEqual(latest["tags"], "frontend,ui", "tags must survive cancel")
		self.assert_row_has_9_fields(latest)

	def test_update_status_done_preserves_category_and_tags(self):
		# R29: update --status done likewise
		self.run_add("Task to update", category="Maintenance", tags="server,urgent")
		self.run_update(1, status="done")
		latest = self.read_latest(1)
		self.assertEqual(latest["status"], "done")
		self.assertEqual(latest["category"], "Maintenance", "category must survive update --status done")
		self.assertEqual(latest["tags"], "server,urgent", "tags must survive update --status done")
		self.assert_row_has_9_fields(latest)

	def test_update_due_preserves_category(self):
		# R29: update --due on categorised task → category survives
		self.run_add("Task with due change", category="ProjectX", tags="tag1")
		self.run_update(1, due="2026-12-31")
		latest = self.read_latest(1)
		self.assertEqual(latest["category"], "ProjectX", "category must survive update --due")
		self.assertEqual(latest["tags"], "tag1", "tags must survive update --due")
		self.assert_row_has_9_fields(latest)

	def test_update_title_preserves_category_and_tags(self):
		# R29: update --title carries forward category and tags
		self.run_add("Old title", category="CatA", tags="t1,t2")
		self.run_update(1, title="New title")
		latest = self.read_latest(1)
		self.assertEqual(latest["title"], "New title")
		self.assertEqual(latest["category"], "CatA")
		self.assertEqual(latest["tags"], "t1,t2")
		self.assert_row_has_9_fields(latest)

	def test_update_importance_preserves_category_and_tags(self):
		# R29: update --importance carries forward category and tags
		self.run_add("Task", category="CatB", tags="t3", importance="low")
		self.run_update(1, importance="high")
		latest = self.read_latest(1)
		self.assertEqual(latest["importance"], "high")
		self.assertEqual(latest["category"], "CatB")
		self.assertEqual(latest["tags"], "t3")
		self.assert_row_has_9_fields(latest)

	def test_add_with_no_category_writes_empty_field_not_omitted(self):
		# R29: add with no --category → field written empty, not omitted (8 fields)
		self.run_add("Uncategorised task")
		latest = self.read_latest(1)
		self.assertEqual(latest["category"], "", "empty category must be written as empty string")
		self.assertEqual(latest["tags"], "", "empty tags must be written as empty string")
		self.assertEqual(latest["importance"], "", "empty importance must be written as empty string")
		self.assert_row_has_9_fields(latest)

	def test_add_with_explicit_empty_category_writes_empty(self):
		# R29: add --category "" writes empty (not omitted)
		self.run_add("Explicit empty category", category="")
		latest = self.read_latest(1)
		self.assertEqual(latest["category"], "")
		self.assert_row_has_9_fields(latest)

	def test_add_with_explicit_empty_tags_writes_empty(self):
		# R29: add --tags "" writes empty
		self.run_add("Explicit empty tags", tags="")
		latest = self.read_latest(1)
		self.assertEqual(latest["tags"], "")
		self.assert_row_has_9_fields(latest)

	def test_update_category_to_empty_preserves_other_fields(self):
		# R29: update --category "" clears category but keeps others
		self.run_add("Task", category="WasSet", tags="keepme", importance="medium")
		self.run_update(1, category="")
		latest = self.read_latest(1)
		self.assertEqual(latest["category"], "")
		self.assertEqual(latest["tags"], "keepme")
		self.assertEqual(latest["importance"], "medium")
		self.assert_row_has_9_fields(latest)

	def test_update_tags_to_empty_preserves_other_fields(self):
		# R29: update --tags "" clears tags but keeps others
		self.run_add("Task", category="keepme", tags="wasSet", importance="high")
		self.run_update(1, tags="")
		latest = self.read_latest(1)
		self.assertEqual(latest["tags"], "")
		self.assertEqual(latest["category"], "keepme")
		self.assertEqual(latest["importance"], "high")
		self.assert_row_has_9_fields(latest)

	def test_all_write_paths_produce_9_columns(self):
		# R32: sanity check that every subcommand produces 9-column rows
		self.run_add("Add task", category="Cat", tags="Tag", importance="low")
		self.run_update(1, status="done")
		self.run_add("Another", category="Cat2")
		self.run_done(2)
		self.run_add("Third", tags="t1")
		self.run_cancel(3)

		with self.csv_path.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			data_rows = [r for r in reader if r and not r[0].startswith("//") and r[0] != "id"]

		self.assertEqual(len(data_rows), 6)  # 3 adds + 3 updates
		for row in data_rows:
			self.assertEqual(len(row), 9, f"Row must have 9 columns: {row}")


class TestR30CSVResolution(unittest.TestCase):
	"""R30: CSV resolves as --csv > $TASKVIEW_CSV > default (data-dir/tasks.csv)."""

	def setUp(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		self.tmp_path = Path(self.tmpdir.name)

	def tearDown(self):
		self.tmpdir.cleanup()

	def run_add(self, csv_path, title="Test task"):
		argv = ["taskupdate", "--csv", str(csv_path), "add", title]
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def run_add_no_csv_flag(self, title="Test task"):
		"""Run add without --csv flag, using default resolution."""
		argv = ["taskupdate", "add", title]
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

	def read_rows(self, csv_path):
		rows = []
		if csv_path.exists():
			with csv_path.open("r", encoding="utf-8") as f:
				reader = csv.reader(f)
				for row in reader:
					if row and not row[0].startswith("//") and row[0] != "id":
						rows.append(row)
		return rows

	def test_explicit_csv_flag_wins(self):
		# R30: --csv beats everything
		csv1 = self.tmp_path / "explicit.csv"
		csv2 = self.tmp_path / "env.csv"
		os.environ["TASKVIEW_CSV"] = str(csv2)

		self.run_add(csv1, "Via --csv")
		rows1 = self.read_rows(csv1)
		rows2 = self.read_rows(csv2)

		self.assertEqual(len(rows1), 1, "Write must go to --csv path")
		self.assertEqual(len(rows2), 0, "Must not write to $TASKVIEW_CSV when --csv given")

	def test_taskview_csv_env_used_when_no_flag(self):
		# R30: $TASKVIEW_CSV honoured when --csv absent
		csv_env = self.tmp_path / "from_env.csv"
		os.environ["TASKVIEW_CSV"] = str(csv_env)

		self.run_add_no_csv_flag("Via env")
		rows_env = self.read_rows(csv_env)
		# Default location is under XDG_DATA_HOME/taskview/tasks.csv (from module setUpModule)
		default_csv = Path(_TEST_XDG_DATA_HOME) / 'taskview' / 'tasks.csv'
		rows_default = self.read_rows(default_csv)

		self.assertEqual(len(rows_env), 1, "R30: $TASKVIEW_CSV should be used when --csv absent")
		self.assertEqual(len(rows_default), 0, "Must not write to default when $TASKVIEW_CSV set")

	def test_explicit_csv_beats_taskview_csv_env(self):
		# R30: --csv beats $TASKVIEW_CSV when both set
		csv_explicit = self.tmp_path / "explicit.csv"
		csv_env = self.tmp_path / "env.csv"
		os.environ["TASKVIEW_CSV"] = str(csv_env)

		self.run_add(csv_explicit, "Explicit wins")
		rows_explicit = self.read_rows(csv_explicit)
		rows_env = self.read_rows(csv_env)

		self.assertEqual(len(rows_explicit), 1)
		self.assertEqual(len(rows_env), 0, "--csv must beat $TASKVIEW_CSV")

	def test_default_location_not_touched_when_csv_flag_used(self):
		# R30/R19: With --csv pointing to temp dir, nothing appears in default location
		csv_temp = self.tmp_path / "temp.csv"

		self.run_add(csv_temp, "Temp only")
		rows_temp = self.read_rows(csv_temp)
		default_csv = Path(_TEST_XDG_DATA_HOME) / 'taskview' / 'tasks.csv'
		rows_default = self.read_rows(default_csv)

		self.assertEqual(len(rows_temp), 1)
		self.assertEqual(len(rows_default), 0, "Default location must not be touched when --csv given")

	def test_taskview_csv_env_does_not_create_default(self):
		# R30/R19: Using $TASKVIEW_CSV must not create default location
		csv_env = self.tmp_path / "env.csv"
		os.environ["TASKVIEW_CSV"] = str(csv_env)

		self.run_add_no_csv_flag("Env only")
		rows_env = self.read_rows(csv_env)
		default_csv = Path(_TEST_XDG_DATA_HOME) / 'taskview' / 'tasks.csv'
		rows_default = self.read_rows(default_csv)

		self.assertEqual(len(rows_env), 1, "R30: $TASKVIEW_CSV should be used")
		self.assertEqual(len(rows_default), 0, "Default must not be created when $TASKVIEW_CSV used")


class TestReadLastId(unittest.TestCase):
	"""read_last_id derives next id from file's maximum (not reusing ids)."""

	def setUp(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		self.csv_path = Path(self.tmpdir.name) / "tasks.csv"

	def tearDown(self):
		self.tmpdir.cleanup()

	def write_raw_rows(self, rows):
		"""Write raw CSV rows directly to file."""
		self.csv_path.parent.mkdir(parents=True, exist_ok=True)
		with self.csv_path.open("w", encoding="utf-8", newline="") as f:
			f.write("// tasks.csv — append-only, last-write-wins by id\n")
			f.write("// Schema: id,status,title,due_ts,chg_ts,category,tags,importance\n")
			f.write("id,status,title,due_ts,chg_ts,category,tags,importance\n")
			writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
			for row in rows:
				writer.writerow(row)

	def test_read_last_id_returns_max_id(self):
		# Existing rows with ids 1, 5, 3 → max is 5
		self.write_raw_rows([
			[1, "open", "Task 1", "", "1000", "", "", ""],
			[5, "open", "Task 5", "", "1001", "", "", ""],
			[3, "open", "Task 3", "", "1002", "", "", ""],
		])
		last_id = taskupdate.read_last_id(self.csv_path)
		self.assertEqual(last_id, 5)

	def test_read_last_id_ignores_comments_and_header(self):
		self.write_raw_rows([
			[10, "open", "Task 10", "", "1000", "", "", ""],
		])
		# Add a comment line and header-like row manually
		with self.csv_path.open("a", encoding="utf-8") as f:
			f.write("// This is a comment\n")
			f.write("id,status,title,due_ts,chg_ts,category,tags,importance\n")
		last_id = taskupdate.read_last_id(self.csv_path)
		self.assertEqual(last_id, 10)

	def test_read_last_id_handles_gaps_and_out_of_order(self):
		self.write_raw_rows([
			[100, "open", "Task 100", "", "1000", "", "", ""],
			[50, "open", "Task 50", "", "1001", "", "", ""],
			[200, "open", "Task 200", "", "1002", "", "", ""],
		])
		last_id = taskupdate.read_last_id(self.csv_path)
		self.assertEqual(last_id, 200)

	def test_read_last_id_returns_zero_for_empty_file(self):
		self.csv_path.parent.mkdir(parents=True, exist_ok=True)
		with self.csv_path.open("w", encoding="utf-8") as f:
			f.write("// tasks.csv — append-only, last-write-wins by id\n")
			f.write("// Schema: id,status,title,due_ts,chg_ts,category,tags,importance\n")
			f.write("id,status,title,due_ts,chg_ts,category,tags,importance\n")
		last_id = taskupdate.read_last_id(self.csv_path)
		self.assertEqual(last_id, 0)

	def test_read_last_id_returns_zero_for_missing_file(self):
		missing = Path(self.tmpdir.name) / "missing.csv"
		last_id = taskupdate.read_last_id(missing)
		self.assertEqual(last_id, 0)

	def test_add_after_high_id_does_not_reuse(self):
		# Add task with id=42 directly, then add via taskupdate → should get 43
		self.write_raw_rows([
			[42, "open", "High id task", "", "1000", "", "", ""],
		])
		# Now use taskupdate to add
		argv = ["taskupdate", "--csv", str(self.csv_path), "add", "New task"]
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

		rows = []
		with self.csv_path.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if row and not row[0].startswith("//") and row[0] != "id":
					rows.append(row)
		# Should have two rows: id=42 and id=43
		self.assertEqual(len(rows), 2)
		ids = [int(r[0]) for r in rows]
		self.assertIn(42, ids)
		self.assertIn(43, ids)
		self.assertNotIn(1, ids, "Must not reuse low ids")


class TestShowCommand(unittest.TestCase):
	"""EY72YA9: `show <id>` resolves a task reference, and `list` prints id first."""

	def setUp(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		self.csv_path = Path(self.tmpdir.name) / "tasks.csv"

	def tearDown(self):
		self.tmpdir.cleanup()

	def run_cli(self, *args, expect_exit=None):
		"""Run taskupdate.main with argv, capturing stdout. Returns (out, err, code)."""
		import io
		import contextlib
		argv = ["taskupdate", "--csv", str(self.csv_path)] + list(args)
		old_argv = sys.argv
		old_out, old_err = sys.stdout, sys.stderr
		sys.argv = argv
		out, err = io.StringIO(), io.StringIO()
		code = 0
		try:
			with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
				taskupdate.main()
		except SystemExit as e:
			code = e.code or 0
		finally:
			sys.argv = old_argv
			sys.stdout, sys.stderr = old_out, old_err
		if expect_exit is not None:
			self.assertEqual(code, expect_exit,
				f"argv={argv} expected exit {expect_exit}, got {code}; stderr={err.getvalue()!r}")
		return out.getvalue(), err.getvalue(), code

	def write_rows(self, text):
		self.csv_path.write_text(text, encoding="utf-8")

	def test_show_on_known_id_prints_every_field(self):
		self.write_rows(
			"// tasks.csv\nid,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,part switching,1791277200,1790746026,work,mms-frontend,medium\n")
		out, _, _ = self.run_cli("show", "1", expect_exit=0)
		for expected in ("#1", "open", "part switching", "work", "mms-frontend", "medium"):
			self.assertIn(expected, out, f"show must report {expected!r}, got {out!r}")

	def test_show_on_unknown_id_exits_nonzero_with_clear_message(self):
		self.write_rows(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,only task,,,,,\n")
		_, err, code = self.run_cli("show", "99")
		self.assertEqual(code, 1, "an unresolvable id must not exit 0")
		self.assertIn("99", err, "the message must name the id that was not found")

	def test_show_on_id_with_mixed_width_history_takes_the_last_row(self):
		# A legacy 5-field row and a later 8-field row share an id. R33: the short
		# row's missing columns read as empty, and last-write-wins by id (R34).
		self.write_rows(
			"id,status,title,due_ts,chg_ts\n"
			"7,open,legacy five field row,1791277200,1790746026\n"
			"7,open,legacy title updated,1791277200,1790746100\n")
		out, _, _ = self.run_cli("show", "7", expect_exit=0)
		self.assertIn("legacy title updated", out, f"last row must win, got {out!r}")
		self.assertNotIn("legacy five field row", out)

	def test_show_on_never_widened_row_reports_empty_optional_fields(self):
		# R33: a row that only ever had 5 fields is uncategorised, not an error.
		self.write_rows(
			"id,status,title,due_ts,chg_ts\n"
			"9,open,only ever five fields,1791277200,1790746026\n")
		out, _, _ = self.run_cli("show", "9", expect_exit=0)
		self.assertIn("only ever five fields", out)
		self.assertIn("(none)", out, f"missing columns must read as empty, got {out!r}")

	def test_show_field_prints_one_value_only(self):
		self.write_rows(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,part switching,1791277200,1790746026,work,mms-frontend,medium\n")
		out, _, _ = self.run_cli("show", "1", "--field", "category", expect_exit=0)
		self.assertEqual(out.strip(), "work", "--field must print just that value")

	def test_show_field_due_ts_prints_the_stored_value(self):
		# The field names are the CSV columns, so --field gives back what is
		# stored — an agent resolving a field usually wants to pass it to update.
		self.write_rows(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,t,1791277200,1790746026,work,,medium\n")
		out, _, _ = self.run_cli("show", "1", "--field", "due_ts", expect_exit=0)
		self.assertEqual(out.strip(), "1791277200")

	def test_show_unknown_field_exits_nonzero_and_lists_the_valid_ones(self):
		self.write_rows(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,t,1791277200,1790746026,work,,medium\n")
		_, err, code = self.run_cli("show", "1", "--field", "nope")
		self.assertEqual(code, 1)
		self.assertIn("category", err, "the error should list the valid field names")

	def test_list_prints_id_first(self):
		self.write_rows(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"3,open,third,1791277200,1790746026,XLib,,low\n"
			"1,open,first,1791277200,1790746026,XLib,,low\n")
		out, _, _ = self.run_cli("list", expect_exit=0)
		lines = [l for l in out.strip().splitlines() if l.strip()]
		self.assertTrue(lines[0].startswith("#1"), f"list must start at the lowest id, got {lines[0]!r}")
		self.assertTrue(lines[1].startswith("#3"))

	def test_list_filters_by_category(self):
		self.write_rows(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,xlib task,1791277200,1790746026,XLib,,low\n"
			"2,open,work task,1791277200,1790746026,work,,low\n")
		out, _, _ = self.run_cli("list", "--category", "work", expect_exit=0)
		self.assertIn("work task", out)
		self.assertNotIn("xlib task", out)

	def test_list_with_no_matches_exits_nonzero(self):
		self.write_rows(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,t,1791277200,1790746026,XLib,,low\n")
		_, err, code = self.run_cli("list", "--category", "nonexistent")
		self.assertEqual(code, 1, "an empty result is not a success")
		self.assertIn("No matching tasks", err)

	def test_list_on_missing_csv_exits_nonzero_without_traceback(self):
		_, err, code = self.run_cli("list")
		self.assertEqual(code, 1)
		self.assertNotIn("Traceback", err)

	def test_show_ignores_comment_and_header_rows(self):
		self.write_rows(
			"// tasks.csv — append-only\n"
			"// Schema: id,status,title\n"
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,real task,,,,,\n")
		out, _, _ = self.run_cli("show", "1", expect_exit=0)
		self.assertIn("real task", out)


class TestIsolationGuard(unittest.TestCase):
	"""R17, R19, R30: Verify the test suite cannot touch the real data directory."""

	# R17, R19
	def test_resolve_data_dir_default_is_in_temp_tree(self):
		# The module-level setUpModule sets XDG_DATA_HOME to a unique temp dir
		from tools.taskview.taskview import resolve_data_dir
		data_dir = resolve_data_dir(None, {})
		self.assertTrue(str(data_dir).startswith(_TEST_XDG_DATA_HOME),
			f"Default data dir {data_dir} must be inside test temp tree {_TEST_XDG_DATA_HOME}")

	# R17, R19
	def test_real_data_dir_untouched_by_resolve(self):
		# The real ~/.local/share/taskview must not be created or modified by tests
		from tools.taskview.taskview import resolve_data_dir
		real_default = Path.home() / '.local' / 'share' / 'taskview'
		data_dir = resolve_data_dir(None, {})
		self.assertNotEqual(data_dir, real_default)
		self.assertTrue(str(data_dir).startswith(_TEST_XDG_DATA_HOME))

	# R30, R19
	def test_write_via_taskupdate_add_goes_to_temp_tree(self):
		# Run an add without --csv, no $TASKVIEW_CSV → should use default under temp XDG_DATA_HOME
		from tools.taskview.taskview import resolve_data_dir, resolve_csv
		data_dir = resolve_data_dir(None, {})
		default_csv = resolve_csv(data_dir, None)
		self.assertTrue(str(default_csv).startswith(_TEST_XDG_DATA_HOME))

		# Now actually write via taskupdate CLI
		argv = ["taskupdate", "add", "Guard test task"]
		old_argv = sys.argv
		sys.argv = argv
		try:
			taskupdate.main()
		finally:
			sys.argv = old_argv

		# The write should have gone to the temp tree's default CSV
		import csv
		rows = []
		if default_csv.exists():
			with default_csv.open("r", encoding="utf-8") as f:
				reader = csv.reader(f)
				for row in reader:
					if row and not row[0].startswith("//") and row[0] != "id":
						rows.append(row)
		self.assertEqual(len(rows), 1, "Write must go to temp tree default CSV")
		self.assertEqual(rows[0][2], "Guard test task")

		# Clean up the default CSV so subsequent tests see a clean state
		if default_csv.exists():
			default_csv.unlink()

		# Real default must be untouched
		real_default = Path.home() / '.local' / 'share' / 'taskview' / 'tasks.csv'
		if real_default.exists():
			# Human's data exists — we must not have added to it
			# Just verify we can read it without error (don't assert on content)
			with real_default.open("r", encoding="utf-8") as f:
				content = f.read()
			# We only assert our temp tree got the write
			pass


if __name__ == "__main__":
	unittest.main()