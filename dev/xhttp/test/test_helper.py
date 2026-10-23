"""
Unit tests for the Accept-Encoding parser in `_/helper.py`.

The server's own `compress` flag is the base decision; this helper is the
filter on top of it. It returns a dict of `{coding: accepted}` parsed from an
`Accept-Encoding` header value, so the caller can decide whether gzip (or any
other coding) is allowed. `None` means the header was absent.

Cases still red pin behaviour the helper does not yet implement (empty-element
handling, malformed q, None, whitespace inside tokens, wildcard q). Red here
means "not done", not "broken test".
"""
import unittest,harness
from xhttp._ import helper

def _ae(value):
	try:
		return helper.accept_encodings(value)
	except Exception as e:
		raise AssertionError(
			"helper.accept_encodings raised %s: %s" % (type(e).__name__, e)
		)

def _gzip_ok(d):
	# None means "no client statement" -> the server's own choice stands (allow).
	if d is None:
		return True
	# gzip is allowed if it is explicitly accepted, or, failing that, if the
	# wildcard is accepted. An explicit refusal (False) beats the wildcard.
	return d.get("gzip", d.get("*", False)) == True

class AcceptedEncodingsParserTest(unittest.TestCase):
	"""The parser, exercised directly. No socket, no request thread."""

	# --- pinned by the note: the contract ---

	def test_absent_returns_none(self):
		self.assertIsNone(_ae(None), "absent -> no client statement (None)")

	def test_empty_returns_empty(self):
		self.assertEqual(_ae(""), {}, "empty -> no accepted codings")

	def test_identity(self):
		self.assertEqual(_ae("identity"), {"identity": True}, "identity -> offered")

	def test_deflate(self):
		self.assertEqual(_ae("deflate"), {"deflate": True}, "deflate -> offered")

	def test_gzip(self):
		self.assertEqual(_ae("gzip"), {"gzip": True}, "gzip -> yes")

	def test_wildcard(self):
		self.assertEqual(_ae("*"), {"*": True}, "* -> yes")

	def test_list(self):
		self.assertEqual(_ae("br, gzip"), {"br": True, "gzip": True}, "br, gzip -> both")

	def test_case_insensitive(self):
		self.assertEqual(_ae("GZIP"), {"gzip": True}, "GZIP -> yes")

	def test_zero_quality_refusal(self):
		self.assertEqual(_ae("gzip;q=0"), {"gzip": False}, "gzip;q=0 -> refused")

	# --- not pinned, but matter in reality ---

	def test_preference_is_not_a_refusal(self):
		self.assertEqual(_ae("gzip;q=0.5"), {"gzip": True}, "gzip;q=0.5 -> yes")

	def test_explicit_refusal_beats_wildcard(self):
		self.assertEqual(_ae("gzip;q=0, *"), {"gzip": False, "*": True}, "gzip;q=0, *")

	def test_wildcard_does_not_rescue_a_refusal(self):
		self.assertEqual(_ae("*, gzip;q=0"), {"*": True, "gzip": False}, "*, gzip;q=0")

	def test_refused_wildcard(self):
		self.assertEqual(_ae("*;q=0"), {"*": False}, "*;q=0 -> refused")

	def test_zero_point_zero_is_a_refusal(self):
		self.assertEqual(_ae("gzip;q=0.0"), {"gzip": False}, "gzip;q=0.0 -> refused")

	def test_spaces_around_separators_are_tolerated(self):
		self.assertEqual(_ae("gzip ; q = 0"), {"gzip": False}, "gzip ; q = 0 -> refused")

	def test_unknown_parameter_does_not_change_the_coding(self):
		self.assertEqual(_ae("gzip;level=9"), {"gzip": True}, "gzip;level=9 -> yes")

	def test_malformed_q_is_ignored(self):
		self.assertEqual(_ae("gzip;q=abc"), {"gzip": True}, "gzip;q=abc -> yes")

	def test_empty_element_is_ignored(self):
		self.assertEqual(_ae("gzip,,deflate"), {"gzip": True, "deflate": True}, "empty element ignored")

	def test_leading_and_trailing_whitespace_is_trimmed(self):
		self.assertEqual(_ae("  gzip  "), {"gzip": True}, "trimmed -> yes")

	def test_substring_is_its_own_coding(self):
		# "x-gzip" is a distinct coding token; it does not make gzip acceptable.
		self.assertEqual(_ae("x-gzip"), {"x-gzip": True}, "x-gzip -> its own entry")
		self.assertFalse(_gzip_ok(_ae("x-gzip")), "x-gzip must not enable gzip")

	def test_gzip_with_other_accepted_codings(self):
		self.assertEqual(_ae("deflate, gzip, br"), {"deflate": True, "gzip": True, "br": True})

	def test_refused_gzip_with_other_coding(self):
		self.assertEqual(_ae("deflate, gzip;q=0"), {"deflate": True, "gzip": False})

	def test_wildcard_with_preference(self):
		self.assertEqual(_ae("*;q=0.5"), {"*": True}, "*;q=0.5 -> yes")

	def test_quality_one(self):
		self.assertEqual(_ae("gzip;q=1"), {"gzip": True}, "gzip;q=1 -> yes")

	def test_small_quality(self):
		self.assertEqual(_ae("gzip;q=0.1"), {"gzip": True}, "gzip;q=0.1 -> yes")

	def test_three_places(self):
		self.assertEqual(_ae("gzip;q=0.000"), {"gzip": False}, "gzip;q=0.000 -> refused")

	def test_case_insensitive_refusal(self):
		self.assertEqual(_ae("GZIP;q=0"), {"gzip": False}, "GZIP;q=0 -> refused")

	def test_tab_whitespace_is_trimmed(self):
		self.assertEqual(_ae("gzip\t"), {"gzip": True}, "gzip\\t -> yes")

	def test_gzip_acceptable_via_wildcard(self):
		self.assertTrue(_gzip_ok(_ae("*")), "wildcard accepts gzip")

	def test_gzip_not_acceptable_when_refused(self):
		self.assertFalse(_gzip_ok(_ae("gzip;q=0")), "refusal wins")

	@harness.decision
	def test_duplicate_coding_one_refusal_settles_it(self):
		"""
		Assumed reading: a refusal on any entry for gzip settles it.
		"""
		self.assertEqual(_ae("gzip, gzip;q=0"), {"gzip": False}, "gzip, gzip;q=0 -> refused (assumed)")

if __name__ == "__main__":
	unittest.main()
