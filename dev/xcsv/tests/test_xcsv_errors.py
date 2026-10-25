"""Error reporting and return values the 2026-10-25 reshape fixed.

Three behaviours were wrong before it, and none of them was covered: the
library's own IOError shadowed the builtin, so a missing file escaped as a
raw FileNotFoundError instead of coming back as an error, and the two bulk
writers threw away the count their docstrings promise.
"""
import os,sys,tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEV = os.path.dirname(os.path.dirname(_HERE))
_ROOT = os.path.dirname(_DEV)
for _entry in (_DEV, _ROOT):
	if _entry not in sys.path:
		sys.path.insert(0, _entry)
from dev.xtest.xtest import contains,equal,raises
from xcsv.xcsv import IOError as CSVIOError,read_line,write_all,write_entries,write_line

_MISSING = os.path.join(tempfile.gettempdir(), "xcsv-no-such-dir", "missing.csv")

def _temp_path():
	fd, path = tempfile.mkstemp(suffix=".csv")
	os.close(fd)
	return path

def test_read_line_reports_a_missing_file():
	tokens, error = read_line(_MISSING)
	equal(tokens, None)
	contains("xcsv-no-such-dir", error)

def test_read_line_raises_the_library_error_when_asked():
	raises(CSVIOError, lambda: read_line(_MISSING, raise_errors=True))

def test_write_line_reports_a_missing_file():
	line, error = write_line(_MISSING, "a", "b")
	equal(line, None)
	contains("xcsv-no-such-dir", error)

def test_write_all_returns_the_count_written():
	path = _temp_path()
	try:
		count, error = write_all(path, [["a", "b"], ["c", "d"]])
		equal(count, 2)
		equal(error, None)
	finally:
		os.unlink(path)

def test_write_entries_returns_the_count_written():
	path = _temp_path()
	try:
		entries = [{"name": "alice", "age": "30"}, {"name": "bob", "age": "40"}]
		count, error = write_entries(path, ["name", "age"], entries)
		equal(count, 2)
		equal(error, None)
	finally:
		os.unlink(path)

if __name__ == "__main__":
	from dev.xtest.xtest import run
	sys.exit(run(__file__))
