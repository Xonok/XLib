def tokenize(line):
	if not line or not line.strip():
		return None, None
	if line.strip().startswith("//"):
		return None, None
	if line.endswith("\r\n"):
		line = line[:-2]
	elif line.endswith("\n") or line.endswith("\r"):
		line = line[:-1]
	in_quotes = False
	comment_pos = -1
	i = 0
	while i < len(line):
		c = line[i]
		if c == '"':
			in_quotes = not in_quotes
		elif c == "/" and not in_quotes and i + 1 < len(line) and line[i + 1] == "/":
			comment_pos = i
			break
		i += 1
	if comment_pos >= 0:
		line = line[:comment_pos].rstrip()
	if not line:
		return None, None
	tokens = []
	i = 0
	n = len(line)
	while i < n:
		c = line[i]
		if c == '"':
			i += 1
			field = []
			while i < n:
				c = line[i]
				if c == '"':
					if i + 1 < n and line[i + 1] == '"':
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
			if i < n and line[i] == ",":
				i += 1
		elif c == ",":
			tokens.append(None)
			i += 1
		else:
			start = i
			while i < n and line[i] != ",":
				i += 1
			field = line[start:i]
			tokens.append(field if field else None)
			if i < n and line[i] == ",":
				i += 1
	if line.endswith(","):
		tokens.append(None)
	return tokens, None
