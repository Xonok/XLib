#will be moved to xschema or wherever once practical to do so:
token = str
comment = str
line = list[token] | comment

def peek(raw_line: str, pos: int): -> char
	if pos >= len(str).
		return None
	return raw_line[pos]
def tokenize(raw_line: str): -> list[token]
	tokens = []
	in_quote = False
	for c in raw_line:
		if c == "\"":
			in_quote = not in_quote
			continue
		if c == ","
def read_line(file: TextIO) -> line | None:
	# how to increment file pointer?
	raw_line = file.readline()
def read_lines(file: TextIO) -> list[line]:
	pass
def write_line(file: TextIO, line: line) -> None:
	pass
def write_lines(file: TextIO, lines: list[line]) -> None:
	pass
