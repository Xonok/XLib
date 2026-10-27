"""Truncating text for previews."""

ELLIPSIS = "..."

def truncate(text,limit):
	"""A string at most `limit` characters, with an ellipsis when it was longer."""
	if len(text) >= limit:
		return text[:limit - len(ELLIPSIS)] + ELLIPSIS
	return text
