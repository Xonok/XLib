def serialize(*args):
	fields = []
	for arg in args:
		if arg is None:
			fields.append("")
		else:
			s = str(arg)
			if "," in s or '"' in s or "\n" in s:
				s = '"' + s.replace('"', '""') + '"'
			fields.append(s)
	return ",".join(fields) + "\n", None
