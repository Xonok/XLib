class ValidationError(Exception):
	"""Raised when a value fails a type check.

	`path` is a list of segments (field names and integer indices) identifying
	where within a nested value the failure occurred.
	"""
	def __init__(self, path, message):
		self.path = path
		self.message = message
		loc = format_path(path)
		super().__init__((loc + ": " if loc else "") + message)

	@property
	def path_str(self):
		return format_path(self.path)

def format_path(path):
	out = ""
	for seg in path:
		if isinstance(seg, int):
			out += "[%d]" % seg
		else:
			out += ("." + seg) if out else seg
	return out
