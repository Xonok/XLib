"""What the arguments said, and what should the program do about it — D13, D14.

The seventh function of the set, and the one that makes the command line
reachable at all. It parses argv, opens the sink, calls `main`, and turns an
unrecognised argument, a missing file or a bundler error into exit code 1.

**It closes what it opened and nothing else.** `--out -` opens nothing, so
stdout is left alone (R5), and a sink `main` was handed is never in this
function's hands to begin with.
"""

import argparse,sys
from tools.pybundle.bundler import main
from tools.pybundle.bundler_imports import IMPORT_FILE_NOT_FOUND

_USAGE = "pybundle --in <path> --out <path|->"

def cli(argv: list) -> int:
	"""Run the bundler over `argv`, which is argv without the program name (D22).

	Returns 0 on success and 1 on anything else, having said why on stderr.
	"""
	parser = argparse.ArgumentParser(prog="pybundle", usage=_USAGE)
	parser.add_argument("--in", dest="entry", required=True)
	parser.add_argument("--out", dest="out", required=True)
	try:
		arguments = parser.parse_args(argv)
	except SystemExit:
		return 1
	try:
		sink = sys.stdout if arguments.out == "-" else open(arguments.out, "w", encoding="utf-8")
	except OSError as problem:
		print(f"pybundle: {problem}", file=sys.stderr)
		return 1
	try:
		main(arguments.entry, sink)
	except (IMPORT_FILE_NOT_FOUND,OSError) as problem:
		print(f"pybundle: {problem}", file=sys.stderr)
		return 1
	finally:
		if sink is not sys.stdout:
			sink.close()
	return 0

if __name__ == "__main__":
	sys.exit(cli(sys.argv[1:]))
