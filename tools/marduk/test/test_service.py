#!/usr/bin/env python3
"""
Tests for the service layer — tools/marduk/_/service.py.

Run with: python3 -m unittest tools.marduk.test.test_service -v

No test here touches the network or the real service: `urlopen` is patched so
the suite is deterministic and safe to run anywhere.

The envelope case is the one that matters most. `/api/session/active` answers
`{"data": {"ses_x": {"type": "running"}}}` rather than the bare mapping its
shape suggests, and reading it without unwrapping yields the literal session id
`"data"` — a panel that silently tracks nothing.
"""
import base64,json,unittest
from unittest.mock import patch
from tools.marduk._ import service

class _FakeConfig:
	"""Stands in for the PosixPath holding service.json; read_text is read-only."""

	def __init__(self,text=None,error=None):
		self._text=text
		self._error=error

	def read_text(self) -> str:
		if self._error:
			raise self._error
		return self._text

class _FakeResponse:
	"""Minimal stand-in for the object `urlopen` hands back."""

	def __init__(self,body:bytes):
		self._body=body

	def read(self) -> bytes:
		return self._body

	def __enter__(self):
		return self

	def __exit__(self,*exc):
		return False

def _serving(payload):
	"""Patch urlopen to answer with `payload`, JSON-encoded."""
	class _Opener:
		def __call__(self,req,timeout=None):
			return _FakeResponse(json.dumps(payload).encode())
	return patch.object(service.urllib.request,"urlopen",_Opener())

class TestAuthHeaders(unittest.TestCase):
	def test_basic_auth_is_user_opencode(self):
		"""The service accepts exactly this user; anything else 401s."""
		headers=service.auth_headers("hunter2")
		expected=base64.b64encode(b"opencode:hunter2").decode()
		self.assertEqual(headers["Authorization"],f"Basic {expected}")

	def test_password_is_not_leaked_into_the_header_verbatim(self):
		self.assertNotIn("hunter2",service.auth_headers("hunter2")["Authorization"])

class TestPassword(unittest.TestCase):
	def test_missing_config_yields_empty_string(self):
		"""A missing config must not raise; the caller reports the error."""
		with patch.object(service,"SERVICE_CONFIG",_FakeConfig(error=OSError("gone"))):
			self.assertEqual(service.password(),"")

	def test_malformed_config_yields_empty_string(self):
		with patch.object(service,"SERVICE_CONFIG",_FakeConfig(text="{not json")):
			self.assertEqual(service.password(),"")

	def test_reads_password_when_present(self):
		with patch.object(service,"SERVICE_CONFIG",_FakeConfig(text='{"password":"s3cret"}')):
			self.assertEqual(service.password(),"s3cret")

class TestAsList(unittest.TestCase):
	def test_bare_list_passes_through(self):
		self.assertEqual(service._as_list([1,2]),[1,2])

	def test_data_envelope_is_unwrapped(self):
		self.assertEqual(service._as_list({"data":[1,2]}),[1,2])

	def test_mapping_envelope_is_not_mistaken_for_a_list(self):
		"""`/api/session/active` is a mapping; coercing it would invent ids."""
		self.assertEqual(service._as_list({"data":{"ses_1":{"type":"running"}}}),[])

	def test_unexpected_shape_yields_empty(self):
		self.assertEqual(service._as_list(None),[])
		self.assertEqual(service._as_list("nonsense"),[])

class TestActiveSessionIds(unittest.TestCase):
	def test_envelope_is_unwrapped(self):
		"""The regression: without this the only id found is the word "data"."""
		with _serving({"data":{"ses_1":{"type":"running"},"ses_2":{"type":"running"}}}):
			self.assertEqual(service.active_session_ids("http://x","pw"),{"ses_1","ses_2"})

	def test_bare_mapping_still_works(self):
		with _serving({"ses_1":{"type":"running"}}):
			self.assertEqual(service.active_session_ids("http://x","pw"),{"ses_1"})

	def test_failed_request_is_none_not_empty(self):
		"""The distinction that stops a blip from retiring every agent."""
		with patch.object(service.urllib.request,"urlopen",side_effect=OSError):
			self.assertIsNone(service.active_session_ids("http://x","pw"))

class TestAllSessions(unittest.TestCase):
	def test_envelope_is_unwrapped(self):
		with _serving({"data":[{"id":"ses_1","agent":"secretary"}]}):
			self.assertEqual(service.all_sessions("http://x","pw"),[{"id":"ses_1","agent":"secretary"}])

	def test_failed_request_is_none_not_empty(self):
		"""None, not []: the watcher must not read a failure as 'none running'."""
		with patch.object(service.urllib.request,"urlopen",side_effect=OSError):
			self.assertIsNone(service.all_sessions("http://x","pw"))

class TestSessionWorkspace(unittest.TestCase):
	def test_directory_is_read_from_a_mapping_location(self):
		self.assertEqual(service.session_workspace({"location":{"directory":"/x/y"}}),"/x/y")

	def test_string_location_is_used_directly(self):
		self.assertEqual(service.session_workspace({"location":"/x/y"}),"/x/y")

	def test_missing_location_yields_empty(self):
		self.assertEqual(service.session_workspace({}),"")
		self.assertEqual(service.session_workspace({"location":None}),"")
		self.assertEqual(service.session_workspace({"location":{}}),"")

class TestGetJson(unittest.TestCase):
	def test_transport_failure_is_none_not_an_exception(self):
		"""Every caller polls in a loop; a raise would kill the panel."""
		with patch.object(service.urllib.request,"urlopen",side_effect=OSError):
			self.assertIsNone(service.get_json("http://x","pw"))

if __name__=="__main__":
	unittest.main()
