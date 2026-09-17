def serialize(*args: str | None):
	fields = []
	for arg in args:
		if arg is None:
			fields.append("")
		else:
			s = str(arg)
			if "," in s or '"' in s or "\n" in s or "\r" in s:
				s = '"' + s.replace('"', '""') + '"'
			fields.append(s)
	return ",".join(fields) + "\n", None
