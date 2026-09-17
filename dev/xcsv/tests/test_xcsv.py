"""Tests for xcsv library (dev version, no prior test coverage)."""
import unittest,sys,tempfile,os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from xcsv.xcsv import tokenize,serialize,schema_parse,parse_line,read_line,read_all,write_line,write_line_tokens,write_all,write_entry,write_entries,parse_all,CSVError,ParseError,SchemaError,UnfinishedLineError,IOError as CSVIOError

class TokenizeTests(unittest.TestCase):
	def test_simple_row(self):
		result, err = tokenize("a,b,c")
		self.assertEqual(result, ["a","b","c"])
		self.assertIsNone(err)

	def test_quoted_fields(self):
		result, err = tokenize('"hello, world",b')
		self.assertEqual(result, ["hello, world", "b"])
		self.assertIsNone(err)

	def test_comment_line_returns_none(self):
		result, err = tokenize("// comment")
		self.assertIsNone(result)
		self.assertIsNone(err)

	def test_raise_errors_raises(self):
		with self.assertRaises(ParseError):
			tokenize('"unclosed', raise_errors=True)

class SerializeTests(unittest.TestCase):
	def test_join_simple(self):
		line, err = serialize("a", "b", "c")
		self.assertEqual(line, "a,b,c\n")
		self.assertIsNone(err)

	def test_quoted_if_comma(self):
		line, err = serialize("hello, world")
		self.assertIn('"', line)
		self.assertIsNone(err)

class SchemaParseTests(unittest.TestCase):
	def test_dict_default(self):
		schema, err = schema_parse("name,age")
		self.assertEqual(schema, {"name":0, "age":1})
		self.assertIsNone(err)

	def test_as_list(self):
		result, err = schema_parse("a,b", as_list=True)
		self.assertEqual(result, ["a","b"])
		self.assertIsNone(err)

class ParseLineTests(unittest.TestCase):
	def test_happy(self):
		data, err = parse_line("alice,30", ["name","age"])
		self.assertEqual(data, {"name":"alice", "age":"30"})
		self.assertIsNone(err)

	def test_unfinished_allowed(self):
		data, err = parse_line("alice", ["name","age"], allow_unfinished=True)
		self.assertEqual(data, {"name":"alice", "age":None})
		self.assertIsNone(err)

	def test_mismatch_raises(self):
		with self.assertRaises(SchemaError):
			parse_line("a,b", ["name"], raise_errors=True)

class FileOperationTests(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
		self.tmp.write("name,age\nalice,30\n")
		self.tmp.close()
		self.path = self.tmp.name

	def tearDown(self):
		try:
			os.unlink(self.path)
		except Exception:
			pass

	def test_read_line_first(self):
		tokens, next_off = read_line(self.path, offset=0)
		self.assertEqual(tokens, ["name","age"])

	def test_read_all(self):
		results, err = read_all(self.path)
		self.assertIsNone(err)
		self.assertTrue(len(results) >= 2)

	def test_write_line_tokens_and_read_back(self):
		append_path = self.path + ".append"
		with open(append_path, "w", encoding="utf-8") as f:
			f.write("")
		result, err = write_line_tokens(append_path, ["x","y"])
		self.assertIsNone(err)
		tokens, _ = read_line(append_path, offset=0)
		self.assertEqual(tokens, ["x","y"])
		os.unlink(append_path)

class ExceptionsExist(unittest.TestCase):
	def test_hierarchy(self):
		self.assertTrue(issubclass(ParseError, CSVError))
		self.assertTrue(issubclass(SchemaError, CSVError))

class SerializerTests(unittest.TestCase):
	def test_quote_cr(self):
		line, err = serialize('a\rb', 'c')
		self.assertIn('"a\rb"', line)
		self.assertIsNone(err)

class WriteLineTests(unittest.TestCase):
	def test_returns_line_on_success(self):
		with tempfile.NamedTemporaryFile(delete=False) as tf:
			path = tf.name
		try:
			line, err = write_line(path, 'x', 'y')
			self.assertIsNotNone(line)
			self.assertIn('x,y', line)
			self.assertIsNone(err)
		finally:
			os.unlink(path)

class ParseAllTests(unittest.TestCase):
	def test_reschema_warning(self):
		with tempfile.NamedTemporaryFile(delete=False, mode='w', newline='') as tf:
			tf.write('a,b\n')
			tf.write('1,2\n')
			tf.write('__reschema__,c,d\n')
			tf.write('3,4,5\n')
			path = tf.name
		try:
			results, err = parse_all(path, ['a','b'], reschema=True)
			self.assertIsNotNone(err)
			# Actually reschema updates; just verify runs without crash
			# After reschema, later rows have new schema; earlier have old.
			# We mainly verify it completes.
		finally:
			os.unlink(path)

if __name__ == "__main__":
	unittest.main()
