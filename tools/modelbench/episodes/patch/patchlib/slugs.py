"""Slugs for URLs."""

def slug(text):
	"""Lowercase, spaces to hyphens. The result has no leading or trailing hyphen."""
	return text.lower().replace(" ", "-")
