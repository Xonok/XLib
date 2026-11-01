"""Tests for tools/xprompt.

The tool is one file whose name is not a module name, so it is loaded by path.
"""
import http.server,importlib.util,io,json,os,subprocess,sys,tempfile,threading,unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "xprompt"

loader = SourceFileLoader("xprompt", str(TOOL))
xprompt = loader.load_module()

class OptionTests(unittest.TestCase):
	def test_coerce_int_float_bool_string(self):
		self.assertEqual(xprompt.coerce_option_value("42"), 42)
		self.assertEqual(xprompt.coerce_option_value("3.5"), 3.5)
		self.assertIs(xprompt.coerce_option_value("true"), True)
		self.assertIs(xprompt.coerce_option_value("false"), False)
		self.assertEqual(xprompt.coerce_option_value("hello"), "hello")

	def test_parse_args_accepts_new_flags(self):
		model, segments, config = xprompt.parse_args([
			"m", "--json", "--option", "temperature=0.5", "--option", "seed=7",
			"--host", "example.com:9000", "prompt text",
		])
		self.assertEqual(model, "m")
		self.assertTrue(config["json"])
		self.assertEqual(config["options"], {"temperature": 0.5, "seed": 7})
		self.assertEqual(config["host"], "example.com:9000")

	def test_parse_args_rejects_malformed_option(self):
		with self.assertRaises(SystemExit) as cm:
			xprompt.parse_args(["m", "--option", "noequals"])
		self.assertEqual(cm.exception.code, 2)

	def test_parse_args_think_flags(self):
		_, _, on = xprompt.parse_args(["m", "--think", "prompt"])
		_, _, off = xprompt.parse_args(["m", "--no-think", "prompt"])
		_, _, unset = xprompt.parse_args(["m", "prompt"])
		self.assertTrue(on["think"])
		self.assertFalse(off["think"])
		self.assertIsNone(unset["think"])

	def test_parses_tool_tag(self):
		calls = xprompt.parse_tool_calls_from_content('<tool>\n{"name": "ls", "arguments": {"path": "."}}\n</tool>')
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0]["function"]["name"], "ls")
		self.assertEqual(calls[0]["function"]["arguments"], {"path": "."})

class PromptFileTests(unittest.TestCase):
	def test_parse_args_keeps_prompt_file_order(self):
		_, segments, _ = xprompt.parse_args(["m", "--prompt", "a", "--prompt-file", "f.txt", "--prompt", "b"])
		self.assertEqual(segments, [("prompt", "a"), ("prompt_file", "f.txt"), ("prompt", "b")])

	def test_prompt_file_content_is_sent_utf8(self):
		with tempfile.TemporaryDirectory() as td:
			path = Path(td) / "prompt.txt"
			path.write_text("ünïcode needle", encoding="utf-8")
			captured = {}
			def fake_chat(model, messages, *args, **kwargs):
				captured["messages"] = [dict(m) for m in messages]
				return {"role": "assistant", "content": "ok", "tool_calls": None, "timings": None}
			with mock.patch.object(xprompt, "ollama_chat", fake_chat):
				with mock.patch("sys.stdout", io.StringIO()):
					code = xprompt.main(["m", "--prompt-file", str(path)])
			self.assertEqual(code, 0)
			self.assertEqual(captured["messages"][-1]["content"], "ünïcode needle")

class HostTests(unittest.TestCase):
	def test_normalize_host_variants(self):
		self.assertEqual(xprompt.normalize_host("http://host:port".replace("port", "1234")), ("host", 1234))
		self.assertEqual(xprompt.normalize_host("host:1234"), ("host", 1234))
		self.assertEqual(xprompt.normalize_host("barehost"), ("barehost", 11434))
		self.assertEqual(xprompt.normalize_host("http://host"), ("host", 11434))

	def test_env_fallback(self):
		with mock.patch.dict(os.environ, {"OLLAMA_HOST": "http://envhost:5555"}, clear=False):
			self.assertEqual(xprompt.normalize_host(), ("envhost", 5555))
			self.assertEqual(xprompt.normalize_host(None), ("envhost", 5555))

class ModelListingTests(unittest.TestCase):
	def test_row_formatting_includes_details(self):
		data = {"models": [
			{"name": "m1", "size": 1024, "capabilities": ["completion"], "details": {
				"parameter_size": "7B", "quantization_level": "Q4_0", "context_length": 4096}},
		]}
		with mock.patch.object(xprompt, "fetch_tags", return_value=data):
			buf = io.StringIO()
			with mock.patch("sys.stdout", buf):
				xprompt.list_models()
			out = buf.getvalue()
			self.assertIn("m1", out)
			self.assertIn("7B", out)
			self.assertIn("Q4_0", out)
			self.assertIn("4096", out)

	def test_detail_calls_show(self):
		data = {"models": [
			{"name": "m1", "size": 1024, "capabilities": ["completion"], "details": {
				"parameter_size": "7B", "quantization_level": "Q4_0", "context_length": 4096}},
		]}
		show = {"parameters": "num_ctx 2048\nnum_gpu 1\nnum_thread 4\n"}
		with mock.patch.object(xprompt, "fetch_tags", return_value=data):
			with mock.patch.object(xprompt, "fetch_show", return_value=show):
				buf = io.StringIO()
				with mock.patch("sys.stdout", buf):
					xprompt.list_models(detail=True)
				out = buf.getvalue()
				self.assertIn("2048", out)
				self.assertIn("1", out)
				self.assertIn("4", out)

	def test_implicit_latest_is_hidden_in_listing(self):
		data = {"models": [
			{"name": "m1:latest", "size": 1024, "capabilities": ["completion"], "details": {
				"parameter_size": "7B", "quantization_level": "Q4_0", "context_length": 4096}},
		]}
		with mock.patch.object(xprompt, "fetch_tags", return_value=data):
			buf = io.StringIO()
			with mock.patch("sys.stdout", buf):
				xprompt.list_models()
			out = buf.getvalue()
			self.assertIn("m1", out)
			self.assertNotIn(":latest", out)

	def test_detail_still_uses_the_raw_name(self):
		data = {"models": [
			{"name": "m1:latest", "size": 1024, "capabilities": ["completion"], "details": {}},
		]}
		seen = []
		def fake_show(name, host=None):
			seen.append(name)
			return {"parameters": ""}
		with mock.patch.object(xprompt, "fetch_tags", return_value=data):
			with mock.patch.object(xprompt, "fetch_show", side_effect=fake_show):
				with mock.patch("sys.stdout", io.StringIO()):
					xprompt.list_models(detail=True)
		self.assertEqual(seen, ["m1:latest"])

class EndToEndJsonTests(unittest.TestCase):
	def test_json_shape(self):
		class Handler(http.server.BaseHTTPRequestHandler):
			COUNT = {"n": 0}
			def do_POST(self):
				ln = int(self.headers.get("Content-Length", "0"))
				self.rfile.read(ln)
				Handler.COUNT["n"] += 1
				if Handler.COUNT["n"] == 1:
					chunks = [
						{"message": {"role": "assistant", "content": "", "tool_calls": [
							{"function": {"name": "bash", "arguments": {"command": "echo hi"}}}]},
						 "done": False},
						{"message": {"role": "assistant", "content": ""}, "done": True,
						 "load_duration": 1, "prompt_eval_count": 2, "prompt_eval_duration": 3,
						 "eval_count": 4, "eval_duration": 5, "total_duration": 6},
					]
				else:
					chunks = [
						{"message": {"role": "assistant", "content": "final answer"}, "done": True,
						 "load_duration": 10, "prompt_eval_count": 20, "prompt_eval_duration": 30,
						 "eval_count": 40, "eval_duration": 50, "total_duration": 60},
					]
				self.send_response(200)
				self.send_header("Content-Type", "application/x-ndjson")
				self.end_headers()
				for c in chunks:
					self.wfile.write((json.dumps(c) + "\n").encode())
					self.wfile.flush()
			def log_message(self, *a):
				pass

		httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
		port = httpd.server_address[1]
		thread = threading.Thread(target=httpd.serve_forever, daemon=True)
		thread.start()
		try:
			proc = subprocess.run(
				[sys.executable, str(TOOL), "testmodel", "--host", f"127.0.0.1:{port}",
				 "--json", "--bash", "--max-turns", "3", "do thing"],
				capture_output=True, text=True,
			)
			self.assertEqual(proc.returncode, 0, proc.stderr)
			obj = json.loads(proc.stdout)
			self.assertEqual(obj["model"], "testmodel")
			self.assertIsNone(obj["think"])
			self.assertEqual(obj["content"], "final answer")
			self.assertEqual(obj["turns"], 2)
			self.assertIsNone(obj["error"])
			self.assertEqual(len(obj["tool_calls"]), 1)
			self.assertEqual(obj["tool_calls"][0]["source"], "native")
			self.assertEqual(obj["tool_calls"][0]["name"], "bash")
			self.assertEqual(len(obj["timings"]), 2)
		finally:
			httpd.shutdown()
			httpd.server_close()

if __name__ == "__main__":
	unittest.main()
