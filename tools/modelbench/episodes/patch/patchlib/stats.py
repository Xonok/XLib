"""Statistics over words."""

from patchlib import tokenizer

def average_word_length(text):
	"""Mean word length; 0.0 when there are no words."""
	words = tokenizer.words(text)
	return sum(len(word) for word in words) / len(words)

def longest_word(text):
	"""The word with the most characters; the first one wins a tie; "" when there are none."""
	words = tokenizer.words(text)
	return max(words) if words else ""
