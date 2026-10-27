"""The vocabulary gate: which categories and tags a machine's store may use.

`<data-dir>/vocab.yaml` lists them, and `taskupdate` refuses a value it does not
list before appending anything. Case, `-` and space are spelling rather than
vocabulary: they are normalised, so the gate refuses unknown words and not
fumbled typing. A missing file means no gate; a broken one is an error on a
write, never a silent pass, and never hides a read.

Every test here works on a temporary store and a temporary data directory, so
the real vocabulary on this machine cannot decide whether the suite passes.
"""
import contextlib,csv,io,os,sys,tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT))

import xtest
from tools.taskview import taskupdate

def _run(argv, csv_path, data_dir):
	"""Run taskupdate with a private store and data directory; return its output and exit code."""
	argv = ["taskupdate", "--csv", str(csv_path)] + list(argv)
	old_argv = sys.argv
	old_data_dir = os.environ.get("TASKVIEW_DATA_DIR")
	os.environ["TASKVIEW_DATA_DIR"] = str(data_dir)
	sys.argv = argv
	out, err = io.StringIO(), io.StringIO()
	code = 0
	try:
		with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
			taskupdate.main()
	except SystemExit as stopped:
		code = stopped.code or 0
	finally:
		sys.argv = old_argv
		if old_data_dir is None:
			os.environ.pop("TASKVIEW_DATA_DIR", None)
		else:
			os.environ["TASKVIEW_DATA_DIR"] = old_data_dir
	return out.getvalue(), err.getvalue(), code

def _vocabulary(data_dir, categories = (), tags = ()):
	"""Write the machine vocabulary as an indented YAML list per kind."""
	lines = ["categories:"]
	lines.extend(f"  - {category}" for category in categories)
	lines.append("tags:")
	lines.extend(f"  - {tag}" for tag in tags)
	(data_dir / "vocab.yaml").write_text("\n".join(lines) + "\n", encoding = "utf-8")

def _rows(csv_path):
	"""The data rows of the store, header and comments excluded."""
	if not csv_path.exists():
		return []
	rows = []
	with csv_path.open("r", encoding = "utf-8") as handle:
		for row in csv.reader(handle):
			if row and not row[0].startswith("//") and row[0] != "id":
				rows.append(row)
	return rows

def _case(vocabulary = True):
	"""A temporary store and data directory, the vocabulary written when asked for."""
	folder = tempfile.TemporaryDirectory()
	data_dir = Path(folder.name)
	csv_path = data_dir / "tasks.csv"
	if vocabulary:
		_vocabulary(data_dir, ["xlib", "traveller"], ["bug", "self_hosted", "taskview"])
	return folder, data_dir, csv_path

def test_an_unknown_category_is_refused_before_the_write():
	folder, data_dir, csv_path = _case()
	with folder:
		_, err, code = _run(["add", "task", "--category", "nonsense"], csv_path, data_dir)
		xtest.equal(code, 1, "an unknown category must not exit 0")
		xtest.contains("nonsense", err)
		xtest.contains("vocab.yaml", err, "the refusal must name the file to edit")
		xtest.equal(_rows(csv_path), [], "a refused write must leave the store untouched")

def test_a_category_in_another_case_is_stored_lowercase():
	folder, data_dir, csv_path = _case()
	with folder:
		_, _, code = _run(["add", "task", "--category", "XLib"], csv_path, data_dir)
		xtest.equal(code, 0)
		xtest.equal(_rows(csv_path)[0][5], "xlib", "case is spelling, not vocabulary")

def test_tags_are_normalised_and_deduplicated():
	folder, data_dir, csv_path = _case()
	with folder:
		_, _, code = _run(["add", "task", "--tags", "Self-Hosted,self hosted,self_hosted"], csv_path, data_dir)
		xtest.equal(code, 0)
		xtest.equal(_rows(csv_path)[0][6], "self_hosted")

def test_an_unknown_tag_is_refused():
	folder, data_dir, csv_path = _case()
	with folder:
		_, err, code = _run(["add", "task", "--tags", "taskview,made_up"], csv_path, data_dir)
		xtest.equal(code, 1)
		xtest.contains("made_up", err)
		xtest.equal(_rows(csv_path), [])

def test_an_empty_category_clears_without_a_refusal():
	folder, data_dir, csv_path = _case()
	with folder:
		_run(["add", "task", "--category", "xlib"], csv_path, data_dir)
		_, _, code = _run(["update", "1", "--category", ""], csv_path, data_dir)
		xtest.equal(code, 0)
		xtest.equal(_rows(csv_path)[-1][5], "", "clearing is legal (SPEC R2)")

def test_a_malformed_vocabulary_is_an_error_on_a_write():
	folder, data_dir, csv_path = _case()
	with folder:
		(data_dir / "vocab.yaml").write_text("- xlib\n", encoding = "utf-8")
		_, err, code = _run(["add", "task", "--category", "xlib"], csv_path, data_dir)
		xtest.equal(code, 1, "a vocabulary that is not a mapping must not silently disable the gate")
		xtest.contains("malformed", err)

def test_a_malformed_vocabulary_does_not_hide_a_read():
	folder, data_dir, csv_path = _case(vocabulary = False)
	with folder:
		csv_path.write_text(
			"id,status,title,due_ts,chg_ts,category,tags,importance\n"
			"1,open,readable,,,,,\n", encoding = "utf-8")
		(data_dir / "vocab.yaml").write_text("- xlib\n", encoding = "utf-8")
		out, _, code = _run(["show", "1"], csv_path, data_dir)
		xtest.equal(code, 0, "a broken vocabulary must not break reads")
		xtest.contains("readable", out)

def test_without_a_vocabulary_file_any_value_is_accepted():
	folder, data_dir, csv_path = _case(vocabulary = False)
	with folder:
		_, _, code = _run(["add", "task", "--category", "anything", "--tags", "whatever"], csv_path, data_dir)
		xtest.equal(code, 0, "the gate is opt-in per machine")

def test_keep_chg_ts_makes_a_correction_not_a_completion():
	folder, data_dir, csv_path = _case()
	with folder:
		_run(["add", "task", "--category", "traveller"], csv_path, data_dir)
		before = _rows(csv_path)[-1][4]
		_, _, code = _run(["update", "1", "--category", "xlib", "--keep-chg-ts"], csv_path, data_dir)
		xtest.equal(code, 0)
		xtest.equal(_rows(csv_path)[-1][4], before, "a correction must not move PACE's done counts")

def test_a_list_filter_is_normalised_like_the_stored_value():
	folder, data_dir, csv_path = _case()
	with folder:
		_run(["add", "task", "--category", "xlib"], csv_path, data_dir)
		out, _, code = _run(["list", "--category", "XLib"], csv_path, data_dir)
		xtest.equal(code, 0, "the filter must find the row stored in house spelling")
		xtest.contains("task", out)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
