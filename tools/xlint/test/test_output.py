"""Tests for `xlint --output` / `-o`: the report written to a file.

The file holds exactly what the terminal report holds; when there are no issues
it is empty (size 0). Writes are atomic.
"""
import os,subprocess,sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest

XLINT = REPO / "tools" / "xlint" / "xlint.py"

def _checkout(folder, name = "repo"):
	root = Path(folder) / name
	root.mkdir(parents = True)
	(root / ".git").mkdir()
	(root / "code.py").write_text("x = 1 \n", encoding = "utf-8")
	return root

def test_output_file_holds_the_report_when_there_are_findings():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		out = Path(folder) / "out.txt"
		result = subprocess.run([sys.executable, str(XLINT), str(root), "-o", str(out)],
			capture_output = True, text = True)
		xtest.equal(result.returncode, 1)
		xtest.true(out.exists(), "the output file is created")
		text = out.read_text(encoding = "utf-8")
		xtest.contains("code.py", text)
		xtest.contains("trailing", text)

def test_output_file_is_empty_when_clean():
	with tempfile.TemporaryDirectory() as folder:
		root = Path(folder) / "repo"
		root.mkdir()
		(root / ".git").mkdir()
		(root / "code.py").write_text("x = 1\n", encoding = "utf-8")
		out = Path(folder) / "out.txt"
		out.write_text("stale content\n", encoding = "utf-8")
		result = subprocess.run([sys.executable, str(XLINT), str(root), "-o", str(out)],
			capture_output = True, text = True)
		xtest.equal(result.returncode, 0)
		xtest.equal(out.read_text(encoding = "utf-8"), "", "clean run truncates the file to empty")
		xtest.equal(os.path.getsize(out), 0)

def test_output_file_is_created_in_a_missing_parent_directory():
	with tempfile.TemporaryDirectory() as folder:
		root = Path(folder) / "repo"
		root.mkdir()
		(root / ".git").mkdir()
		(root / "code.py").write_text("x = 1\n", encoding = "utf-8")
		out = Path(folder) / "nested" / "dir" / "out.txt"
		result = subprocess.run([sys.executable, str(XLINT), str(root), "-o", str(out)],
			capture_output = True, text = True)
		xtest.equal(result.returncode, 0)
		xtest.true(out.exists(), "parent directories are created")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
