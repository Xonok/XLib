"""
Config validation tests: config_valid.

SPEC.md mentions config_valid is untested. These tests cover the validation
function that checks file-serving config structure.
"""

import unittest,harness
from xhttp import xhttp
class ConfigValidTest(unittest.TestCase):
	"""config_valid: validates file-serving config dictionary."""

	@unittest.expectedFailure
	def test_valid_config_returns_true(self):
		"""A properly structured config returns (True, None).

		EXPECTED FAILURE: config_valid has a bug - it checks config["folder"]
		instead of v["folder"] (the per-entry value). Bug in xhttp.py:314-319.
		"""
		config = {
			".html": {"folder": "www", "mime": "text/html", "compress": True},
			".css": {"folder": "www", "mime": "text/css", "compress": True},
			".js": {"folder": "www", "mime": "application/javascript", "compress": True},
		}
		valid, err = xhttp.config_valid(config)
		self.assertTrue(valid)
		self.assertIsNone(err)

	def test_non_dict_config_rejected(self):
		"""Non-dictionary config is rejected."""
		for invalid in [None, "string", 123, [], ["a", "b"]]:
			valid, err = xhttp.config_valid(invalid)
			self.assertFalse(valid)
			self.assertEqual(err, "Config must be a dictionary")

	def test_key_must_start_with_dot(self):
		"""Config keys must start with a dot (file extension)."""
		config = {"html": {"folder": "", "mime": "text/html", "compress": False}}
		valid, err = xhttp.config_valid(config)
		self.assertFalse(valid)
		self.assertEqual(err, "Each config entry must have a key that starts with a dot, because the keys are file formats.")

	def test_missing_folder_key_rejected(self):
		"""Each entry must have 'folder' key."""
		config = {".html": {"mime": "text/html", "compress": False}}
		valid, err = xhttp.config_valid(config)
		self.assertFalse(valid)
		self.assertEqual(err, "Each config entry must contain these keys: folder, mime, compress")

	def test_missing_mime_key_rejected(self):
		"""Each entry must have 'mime' key."""
		config = {".html": {"folder": "www", "compress": False}}
		valid, err = xhttp.config_valid(config)
		self.assertFalse(valid)
		self.assertEqual(err, "Each config entry must contain these keys: folder, mime, compress")

	def test_missing_compress_key_rejected(self):
		"""Each entry must have 'compress' key."""
		config = {".html": {"folder": "www", "mime": "text/html"}}
		valid, err = xhttp.config_valid(config)
		self.assertFalse(valid)
		self.assertEqual(err, "Each config entry must contain these keys: folder, mime, compress")

	@unittest.expectedFailure
	def test_folder_must_be_string(self):
		"""'folder' value must be a string.

		EXPECTED FAILURE: config_valid has a bug - it checks config["folder"]
		instead of v["folder"]. Bug in xhttp.py:314.
		"""
		config = {".html": {"folder": 123, "mime": "text/html", "compress": False}}
		valid, err = xhttp.config_valid(config)
		self.assertFalse(valid)
		self.assertEqual(err, "Key 'folder' must be a string.")

	@unittest.expectedFailure
	def test_mime_must_be_string(self):
		"""'mime' value must be a string.

		EXPECTED FAILURE: config_valid has a bug - it checks config["mime"]
		instead of v["mime"]. Bug in xhttp.py:316.
		"""
		config = {".html": {"folder": "www", "mime": 123, "compress": False}}
		valid, err = xhttp.config_valid(config)
		self.assertFalse(valid)
		self.assertEqual(err, "Key 'mime' must be a string.")

	@unittest.expectedFailure
	def test_compress_must_be_bool(self):
		"""'compress' value must be a boolean.

		EXPECTED FAILURE: config_valid has a bug - it checks config["compress"]
		instead of v["compress"]. Bug in xhttp.py:318.
		"""
		config = {".html": {"folder": "www", "mime": "text/html", "compress": "yes"}}
		valid, err = xhttp.config_valid(config)
		self.assertFalse(valid)
		self.assertEqual(err, "Key 'compress' must be a bool.")

	def test_empty_config_is_valid(self):
		"""Empty config dict is valid (no file types configured)."""
		config = {}
		valid, err = xhttp.config_valid(config)
		self.assertTrue(valid)
		self.assertIsNone(err)

	@unittest.expectedFailure
	def test_folder_can_be_empty_string(self):
		"""'folder' can be empty string (means current directory).

		EXPECTED FAILURE: config_valid has a bug - it checks config["folder"]
		instead of v["folder"]. Bug in xhttp.py:314.
		"""
		config = {".html": {"folder": "", "mime": "text/html", "compress": False}}
		valid, err = xhttp.config_valid(config)
		self.assertTrue(valid)
		self.assertIsNone(err)

	@unittest.expectedFailure
	def test_compress_true_and_false_both_valid(self):
		"""Both True and False are valid for compress.

		EXPECTED FAILURE: config_valid has a bug - it checks config["compress"]
		instead of v["compress"]. Bug in xhttp.py:318.
		"""
		for val in [True, False]:
			config = {".html": {"folder": "www", "mime": "text/html", "compress": val}}
			valid, err = xhttp.config_valid(config)
			self.assertTrue(valid, f"compress={val} should be valid")
			self.assertIsNone(err)
class ConfigValidEdgeTest(unittest.TestCase):
	"""
	Edge cases for config validation.

	Run with `python3 dev/xhttp/test/run.py` to include, `--core` to skip.
	"""

	@harness.edge
	@unittest.expectedFailure
	def test_extra_keys_allowed(self):
		"""Extra keys in config entry are allowed (not rejected).

		EXPECTED FAILURE: config_valid has a bug - it checks config["folder"]
		instead of v["folder"]. Bug in xhttp.py:314.
		"""
		config = {
			".html": {
				"folder": "www",
				"mime": "text/html",
				"compress": True,
				"cache": "max-age=3600", # Extra key like real files.json has
				"custom": "value"
			}
		}
		valid, err = xhttp.config_valid(config)
		self.assertTrue(valid, "Extra keys should be allowed")

	@harness.edge
	def test_unicode_keys_and_values(self):
		"""Unicode in keys and values is handled."""
		config = {"日本語": {"folder": "www", "mime": "text/html", "compress": False}}
		valid, err = xhttp.config_valid(config)
		# Key doesn't start with dot, should fail
		self.assertFalse(valid)
if __name__ == "__main__":
	unittest.main()
