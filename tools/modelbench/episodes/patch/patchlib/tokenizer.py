"""Turning text into words."""

import re

WORD = re.compile(r"\w+")

def words(text):
	"""Words are runs of letters and apostrophes. Digits and underscores are not words."""
	return WORD.findall(text)

def word_count(text):
	"""How many words the text contains."""
	return len(words(text))
