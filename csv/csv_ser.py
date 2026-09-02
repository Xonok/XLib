def serialize(*args):
	"""Serialize arguments into a CSV line.

	Returns (string, error) where:
	- string is the CSV line (with trailing newline), or None on error
	- error is None on success, or a string describing the error
	"""
	fields = []
	for arg in args:
		if arg is None:
			fields.append("")
		else:
			s = str(arg)
			if ',' in s or '"' in s or '\n' in s:
				s = '"' + s.replace('"', '""') + '"'
			fields.append(s)
	return (",".join(fields) + "\n", None)
