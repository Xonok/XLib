def tokenize(line: str):
	if not line or not line.strip():
		return None, None

	# Handle line endings: \r\n, \n, \r
	if line.endswith("\r\n"):
		line = line[:-2]
	elif line.endswith("\n") or line.endswith("\r"):
		line = line[:-1]

	# Comment detection: only at line start (after stripping leading whitespace).
	# This replaces the in-loop `c == "/" and not in_quotes and peek("/")` test,
	# which was the second of peek's two call sites. The rewrite is sound — a
	# comment cannot start mid-field, so a line-start test is the stronger check —
	# but it is why peek now has one caller rather than two, and one caller looks
	# like a pattern that never repeated. It did: it was factored at 369b0bc and
	# removed at f0b81d0, both changes in review passes months apart. Kept on the
	# legibility ground (doc/style/common.md: "a pattern that takes >5 seconds to
	# read is a candidate even once"), not on a repetition count.
	stripped = line.lstrip()
	if stripped.startswith("//"):
		return None, None

	tokens: list[str | None] = []
	i = 0
	line_len = len(line)

	def peek(c: str) -> bool:
		"""True when the next character past position i is c. Names the lookahead,
		so the escaped-quote test below reads as a question rather than arithmetic."""
		return i + 1 < line_len and line[i + 1] == c

	def at_comma() -> bool:
		"""True when the current character is a delimiter, or the line has run out."""
		return i < line_len and line[i] == ","

	while i < line_len:
		c = line[i]
		if c == '"':
			i += 1
			field = []
			while i < line_len:
				c = line[i]
				if c == '"':
					if peek('"'):
						field.append('"')
						i += 2
					else:
						i += 1
						break
				else:
					field.append(c)
					i += 1
			else:
				return None, "unterminated quoted field"
			tokens.append("".join(field))
			if at_comma():
				i += 1
		elif at_comma():
			tokens.append(None)
			i += 1
		else:
			start = i
			while i < line_len and not at_comma():
				i += 1
			field = line[start:i]
			tokens.append(field if field else None)
			if at_comma():
				i += 1

	if line.endswith(","):
		tokens.append(None)

	return tokens, None
