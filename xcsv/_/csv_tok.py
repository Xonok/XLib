def tokenize(line: str):
	if not line or not line.strip():
		return None, None

	# Handle line endings: \r\n, \n, \r
	if line.endswith("\r\n"):
		line = line[:-2]
	elif line.endswith("\n") or line.endswith("\r"):
		line = line[:-1]

	# Comment detection: only at line start (after stripping leading whitespace)
	stripped = line.lstrip()
	if stripped.startswith("//"):
		return None, None

	tokens: list[str | None] = []
	i = 0
	line_len = len(line)
	while i < line_len:
		c = line[i]
		if c == '"':
			i += 1
			field = []
			while i < line_len:
				c = line[i]
				if c == '"':
					if i + 1 < line_len and line[i + 1] == '"':
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
			if i < line_len and line[i] == ",":
				i += 1
		elif c == ",":
			tokens.append(None)
			i += 1
		else:
			start = i
			while i < line_len and line[i] != ",":
				i += 1
			field = line[start:i]
			tokens.append(field if field else None)
			if i < line_len and line[i] == ",":
				i += 1

	if line.endswith(","):
		tokens.append(None)

	return tokens, None
