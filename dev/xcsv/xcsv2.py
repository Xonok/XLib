"""
Fresh rewrite.
No AI code for implementation.
No AI code for tests. (experiment)

Features required:
Raw mode - Read and write lines of CSV.
Table mode - use schema to return results as dict or struct(class?).
Stream mode - read and write files, keep file open.
Roundtrippable - you can read and write a file in the same mode, getting the same output,
only guaranteed when the file was previously written with the same version of xcsv.

Open questions:
*How to deal with a mix of quoted and unquoted fields?
*Can a token start or end with a space? Well, mostly a detail of the other question^

Decided, not implemented:
*Nothing right now.

Low-prio ideas:
*Option on each function to return exceptions as values?
"""
from typing import TextIO
from ._2 import raw,table,stream,err

#will be moved to xschema or wherever once practical to do so:
token = str
comment = str
line = list[token] | comment

#raw mode
def read_line(file: TextIO) -> line | None:
	#increments file pointer; can be called again to get the next line.
	return raw.read_line(file)
def read_lines(file: TextIO) -> list[line]:
	return raw.read_lines(file)
def write_line(file: TextIO, line: line) -> None:
	raw.write_line(file,line)
def write_lines(file: TextIO, lines: list[line]) -> None:
	raw.write_lines(file,lines)

err_CSVNoFile = err.CSVNoFile
#LATER: other file-related errors
err_CSVNotToken = err.CSVNotToken
