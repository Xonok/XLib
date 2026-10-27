import unittest
from patchlib import slugs,stats,tokenizer,truncate

class WordTest(unittest.TestCase):
	def test_words(self):
		self.assertEqual(tokenizer.words("the quick brown fox"),["the","quick","brown","fox"])

	def test_count(self):
		self.assertEqual(tokenizer.word_count("one two three"),3)

class SlugTest(unittest.TestCase):
	def test_slug(self):
		self.assertEqual(slugs.slug("Hello World"),"hello-world")

class TruncateTest(unittest.TestCase):
	def test_short_text_is_unchanged(self):
		self.assertEqual(truncate.truncate("hello",10),"hello")

	def test_long_text_is_truncated(self):
		self.assertEqual(truncate.truncate("hello world",8),"hello...")

class StatsTest(unittest.TestCase):
	def test_average(self):
		self.assertAlmostEqual(stats.average_word_length("one two three"),3.6666667,places=6)

	def test_longest(self):
		self.assertEqual(stats.longest_word("a bb ccc"),"ccc")

if __name__ == "__main__":
	unittest.main()
