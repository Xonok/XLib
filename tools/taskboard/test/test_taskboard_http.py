"""The HTTP surface of taskboard: payload, headers, errors, edits and auth.

Each test starts the real command on an ephemeral port and talks to it over a
socket, because the spec pins the command and the startup line but no server
factory. The requirement each test traces to is in its name.
"""
import datetime,os,socket,sys,threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import xtest
from _harness import PAYLOAD_KEYS,Store,start_server,start_with_args,run_taskboard,get,post_json,request,due_payload,cookie,free_port,seed_store

TOKEN = "0123456789abcdef"

def _start_without_csv(args, env=None):
	return start_with_args(args, env=env)

def _ts(year, month, day, hour=12, minute=0):
	return int(datetime.datetime(year, month, day, hour, minute).timestamp())

def _find(payload, task_id):
	return next(task for task in payload["tasks"] if task["id"] == task_id)

def _error_body(response):
	payload = response.json()
	xtest.kind(payload.get("error"), str)
	xtest.kind(payload.get("message"), str)
	return payload

def test_R7_get_tasks_returns_200_and_json_content_type():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			response = get(server, "/api/tasks")
			xtest.equal(response.status, 200)
			xtest.equal(response.header("Content-Type"), "application/json; charset=utf-8")

def test_R7_get_tasks_has_the_documented_payload():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			payload = get(server, "/api/tasks").json()
			xtest.equal(set(payload), {"now", "store", "summary", "tasks"})
			xtest.kind(payload["now"], int)
			xtest.kind(payload["store"]["path"], str)
			xtest.equal(set(payload["summary"]), {"open", "overdue", "today", "this_week", "later", "undated"})

def test_R7_non_ascii_text_is_preserved_as_utf8():
	with Store() as store:
		store.add(1, title="café ünïcode")
		with start_server(store) as server:
			body = get(server, "/api/tasks").body.decode("utf-8")
			xtest.contains("café ünïcode", body)

def test_R7_get_tasks_rereads_the_store_on_every_request():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			first = get(server, "/api/tasks").json()
			store.add(2)
			second = get(server, "/api/tasks").json()
			xtest.equal(len(second["tasks"]), len(first["tasks"]) + 1)

def test_R7_a_vanished_store_returns_503_and_names_the_path():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			store.csv.unlink()
			response = get(server, "/api/tasks")
			xtest.equal(response.status, 503)
			xtest.contains(str(store.csv), response.json()["message"])

def test_R7_a_vanished_store_is_not_recreated():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			store.csv.unlink()
			get(server, "/api/tasks")
			xtest.true(not store.csv.exists(), "a GET must not recreate the store")

def test_R8_get_tasks_sends_an_etag():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.true(get(server, "/api/tasks").header("ETag"))

def test_R8_a_matching_if_none_match_returns_304_with_no_body():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			etag = get(server, "/api/tasks").header("ETag")
			response = get(server, "/api/tasks", {"If-None-Match": etag})
			xtest.equal(response.status, 304)
			xtest.equal(response.body, b"")

def test_R8_an_unmatched_if_none_match_returns_200():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(get(server, "/api/tasks", {"If-None-Match": "no-such-tag"}).status, 200)

def test_R8_a_write_changes_the_etag():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			before = get(server, "/api/tasks").header("ETag")
			store.add(2)
			after = get(server, "/api/tasks").header("ETag")
			xtest.not_equal(before, after)

def test_R8_the_etag_follows_the_store_modification_time():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			before = get(server, "/api/tasks").header("ETag")
			os.utime(store.csv, (1234567890, 1234567890))
			after = get(server, "/api/tasks").header("ETag")
			xtest.not_equal(before, after)

def test_R9_a_body_over_64_kib_is_413():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			body = b'{"id":1,"value":"' + b"x" * (70 * 1024) + b'","expected_chg_ts":1000}'
			response = request(server.base + "/api/due", "POST", body, {"Content-Type": "application/json"})
			xtest.equal(response.status, 413)

def test_R9_a_non_object_body_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", []).status, 400)

def test_R9_malformed_json_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			response = request(server.base + "/api/due", "POST", b"{", {"Content-Type": "application/json"})
			xtest.equal(response.status, 400)

def test_R9_a_missing_id_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", {"value": "2026-10-27", "expected_chg_ts": 1000}).status, 400)

def test_R9_a_missing_value_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", {"id": 1, "expected_chg_ts": 1000}).status, 400)

def test_R9_a_missing_expected_chg_ts_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", {"id": 1, "value": "2026-10-27"}).status, 400)

def test_R9_a_string_id_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", {"id": "1", "value": "2026-10-27", "expected_chg_ts": 1000}).status, 400)

def test_R9_a_non_string_value_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", {"id": 1, "value": 27, "expected_chg_ts": 1000}).status, 400)

def test_R9_a_non_integer_expected_chg_ts_is_400():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", {"id": 1, "value": "2026-10-27", "expected_chg_ts": "1000"}).status, 400)

def test_R9_unknown_keys_are_ignored():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			response = post_json(server, "/api/due", {"id": 1, "value": "2026-10-27", "expected_chg_ts": 1000, "force": True})
			xtest.equal(response.status, 200)

def test_R10_a_valid_absolute_date_edits_the_task():
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		with start_server(store) as server:
			payload = post_json(server, "/api/due", due_payload(1, "2026-10-27", 1000)).json()
			xtest.equal(_find(payload, 1)["due_date"], "2026-10-27")

def test_R10_an_invalid_value_is_400_with_the_grammar():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			response = post_json(server, "/api/due", due_payload(1, "tomorrow", 1000))
			xtest.equal(response.status, 400)
			xtest.contains("YYYY-MM-DD", response.json()["message"])

def test_R11_post_returns_the_full_payload_after_the_append():
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		with start_server(store) as server:
			payload = post_json(server, "/api/due", due_payload(1, "2026-10-27", 1000)).json()
			xtest.equal(set(payload), {"now", "store", "summary", "tasks"})
			xtest.equal(_find(payload, 1)["due_ts"], _ts(2026, 10, 27))

def test_R11_an_unknown_id_is_404():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", due_payload(99, "2026-10-27", 1000)).status, 404)

def test_R11_a_done_task_is_409():
	with Store() as store:
		store.add(1, status="done", chg_ts=1000)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", due_payload(1, "2026-10-27", 1000)).status, 409)

def test_R11_a_stale_token_is_409():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			xtest.equal(post_json(server, "/api/due", due_payload(1, "2026-10-27", 999)).status, 409)

def test_R12_a_conflict_body_carries_the_current_task_in_payload_shape():
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		with start_server(store) as server:
			payload = post_json(server, "/api/due", due_payload(1, "2026-10-27", 999)).json()
			xtest.equal(payload["error"], "conflict")
			xtest.equal(set(payload["task"]), PAYLOAD_KEYS)
			xtest.equal(payload["task"]["due_date"], "2026-10-20")

def test_R12_a_forced_write_is_still_refused():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			response = post_json(server, "/api/due", {"id": 1, "value": "2026-10-27", "expected_chg_ts": 999, "force": True})
			xtest.equal(response.status, 409)

def test_R11_a_vanished_store_is_409_and_not_recreated():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			store.csv.unlink()
			response = post_json(server, "/api/due", due_payload(1, "2026-10-27", 1000))
			xtest.equal(response.status, 409)
			xtest.true(not store.csv.exists(), "a failed write must not create the store")

def test_R11_clearing_the_due_date_returns_a_null_due():
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		with start_server(store) as server:
			payload = post_json(server, "/api/due", due_payload(1, "none", 1000)).json()
			xtest.equal(_find(payload, 1)["due_ts"], None)

def test_R28_two_writes_for_one_row_are_serialised():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			barrier = threading.Barrier(2)
			statuses = []
			def write(value):
				barrier.wait()
				statuses.append(post_json(server, "/api/due", due_payload(1, value, 1000)).status)
			threads = [threading.Thread(target=write, args=(value,)) for value in ("2026-10-27", "2026-10-28")]
			for thread in threads:
				thread.start()
			for thread in threads:
				thread.join()
			xtest.equal(sorted(statuses), [200, 409])

def test_R13_an_error_response_is_json_with_error_and_message():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			_error_body(get(server, "/no-such-route"))

def test_R13_an_unknown_route_is_404():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(get(server, "/no-such-route").status, 404)

def test_R13_get_on_the_edit_route_is_405_with_allow():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			response = get(server, "/api/due")
			xtest.equal(response.status, 405)
			xtest.contains("POST", response.header("Allow"))

def test_R13_post_on_a_page_route_is_405_with_allow():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			response = request(server.base + "/", "POST", b"", {"Content-Type": "application/json"})
			xtest.equal(response.status, 405)
			xtest.contains("GET", response.header("Allow"))

def test_R13_a_post_without_a_json_content_type_is_415():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			response = request(server.base + "/api/due", "POST", b"{}", {"Content-Type": "text/plain"})
			xtest.equal(response.status, 415)

def test_R25_a_foreign_origin_is_403():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			response = post_json(server, "/api/due", due_payload(1, "2026-10-27", 1000), {"Origin": "http://evil.example"})
			xtest.equal(response.status, 403)

def test_R25_the_matching_origin_is_accepted():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			response = post_json(server, "/api/due", due_payload(1, "2026-10-27", 1000), {"Origin": server.base})
			xtest.equal(response.status, 200)

def test_R14_the_page_is_html():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(get(server, "/").header("Content-Type"), "text/html; charset=utf-8")

def test_R14_the_script_is_javascript():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(get(server, "/board.js").header("Content-Type"), "text/javascript; charset=utf-8")

def test_R14_the_stylesheet_is_css():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.equal(get(server, "/board.css").header("Content-Type"), "text/css; charset=utf-8")

def test_R14_the_edit_route_returns_json():
	with Store() as store:
		store.add(1, chg_ts=1000)
		with start_server(store) as server:
			response = post_json(server, "/api/due", due_payload(1, "2026-10-27", 1000))
			xtest.equal(response.header("Content-Type"), "application/json; charset=utf-8")

def test_R14_a_get_never_mutates_the_store():
	with Store() as store:
		store.add(1)
		before = store.fingerprint()
		with start_server(store) as server:
			get(server, "/")
			get(server, "/board.js")
			get(server, "/board.css")
			get(server, "/api/tasks")
		xtest.equal(store.fingerprint(), before)

def test_R26_starting_and_reading_create_no_extra_files():
	with Store() as store:
		store.add(1)
		before = store.names()
		with start_server(store) as server:
			get(server, "/api/tasks")
		xtest.equal(store.names(), before)

def test_R22_every_response_carries_the_security_headers():
	csp = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			for path in ("/", "/board.js", "/board.css", "/api/tasks"):
				response = get(server, path)
				xtest.equal(response.header("X-Content-Type-Options"), "nosniff", path)
				xtest.equal(response.header("Referrer-Policy"), "no-referrer", path)
				xtest.equal(response.header("Content-Security-Policy"), csp, path)

def test_R22_the_page_and_the_api_are_not_stored():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			xtest.contains("no-store", get(server, "/").header("Cache-Control"))
			xtest.contains("no-store", get(server, "/api/tasks").header("Cache-Control"))

def test_R24_a_non_loopback_bind_without_a_token_exits_1():
	with Store() as store:
		store.add(1)
		code, stdout, stderr = run_taskboard("--csv", store.csv, "--host", "0.0.0.0", "--port", "0")
		xtest.equal(code, 1)
		xtest.contains("token", (stdout + stderr).lower())

def test_R24_a_non_loopback_bind_with_a_short_token_exits_1():
	with Store() as store:
		store.add(1)
		code, stdout, stderr = run_taskboard("--csv", store.csv, "--host", "0.0.0.0", "--port", "0", "--token", "short")
		xtest.equal(code, 1)
		xtest.contains("token", (stdout + stderr).lower())

def test_R24_a_configured_token_is_enforced_on_loopback():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			xtest.equal(get(server, "/").status, 401)

def test_R24_the_startup_url_carries_the_token():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			xtest.contains(TOKEN, server.url)

def test_R24_the_bootstrap_url_sets_the_cookie_and_redirects():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			response = request(server.url)
			header = response.header("Set-Cookie").lower()
			xtest.equal(response.status, 303)
			xtest.equal(response.header("Location"), "/")
			xtest.contains("httponly", header)
			xtest.contains("samesite=strict", header)
			xtest.contains("path=/", header)

def test_R24_the_cookie_grants_access():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			jar = cookie(request(server.url))
			xtest.equal(get(server, "/", {"Cookie": jar}).status, 200)

def test_R24_a_wrong_token_is_401():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			xtest.equal(get(server, "/?token=wrong").status, 401)

def test_R24_a_wrong_cookie_is_401():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			xtest.equal(get(server, "/", {"Cookie": "taskboard=wrong"}).status, 401)

def test_R24_the_token_is_not_in_an_error_body():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			xtest.true(TOKEN.encode() not in get(server, "/").body)

def test_R24_the_token_appears_only_in_the_startup_url():
	with Store() as store:
		store.add(1)
		with start_server(store, token=TOKEN) as server:
			get(server, "/")
			xtest.equal(server.output().count(TOKEN), 1)

def test_R24_a_token_parameter_is_ignored_when_none_is_configured():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			response = get(server, "/?token=whatever")
			xtest.equal(response.status, 200)
			xtest.equal(response.header("Set-Cookie"), None)

def test_R24_localhost_is_loopback():
	with Store() as store:
		store.add(1)
		with start_server(store, host="localhost") as server:
			xtest.equal(get(server, "/").status, 200)

def test_R30_port_zero_binds_an_ephemeral_port():
	with Store() as store:
		store.add(1)
		with start_server(store, port=0) as server:
			xtest.true(int(server.base.rsplit(":", 1)[1]) != 0)

def test_R30_a_specified_port_is_honoured():
	with Store() as store:
		store.add(1)
		port = free_port()
		with start_server(store, port=port) as server:
			xtest.equal(int(server.base.rsplit(":", 1)[1]), port)

def test_R30_a_bind_failure_exits_1_and_does_not_fall_back():
	with Store() as store:
		store.add(1)
		with socket.socket() as held:
			held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			held.bind(("127.0.0.1", 0))
			held.listen(1)
			port = held.getsockname()[1]
			code, stdout, stderr = run_taskboard("--csv", store.csv, "--host", "127.0.0.1", "--port", port)
		xtest.equal(code, 1)
		xtest.true(bool(stdout + stderr), "a bind failure must say something")

def test_R30_the_default_port_is_8780():
	with Store() as store:
		store.add(1)
		with socket.socket() as held:
			held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			try:
				held.bind(("127.0.0.1", 8780))
			except OSError as error:
				raise AssertionError(f"port 8780 is already in use; cannot test the default: {error}")
			held.listen(1)
			code, stdout, stderr = run_taskboard("--csv", store.csv, "--host", "127.0.0.1")
		xtest.equal(code, 1)

def test_R31_starting_prints_the_url_store_path_and_open_count():
	with Store() as store:
		store.add(1)
		store.add(2)
		store.add(3, status="done")
		with start_server(store) as server:
			line = server.startup()
			xtest.contains("http", line)
			xtest.contains(str(store.csv), line)
			xtest.contains("2", line)

def test_R31_sigint_exits_0():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			code = server.stop()
			xtest.equal(code, 0)

def test_R1_the_csv_flag_wins_over_the_environment():
	with Store() as store:
		store.add(1)
		other = Path(store.dir) / "other" / "tasks.csv"
		seed_store(other, 2)
		with start_server(store, env={"TASKVIEW_CSV": str(other)}) as server:
			xtest.contains(str(store.csv), server.startup())
			xtest.true(str(other) not in server.startup())

def test_R1_taskview_csv_environment_resolves_the_store():
	with Store() as store:
		store.add(1)
		with _start_without_csv(["--host", "127.0.0.1", "--port", "0"], env={"TASKVIEW_CSV": str(store.csv)}) as server:
			xtest.contains(str(store.csv), server.startup())

def test_R1_the_data_dir_flag_resolves_tasks_csv():
	with Store() as store:
		store.add(1)
		with _start_without_csv(["--data-dir", str(store.dir), "--host", "127.0.0.1", "--port", "0"]) as server:
			xtest.contains(str(store.csv), server.startup())

def test_R1_taskview_data_dir_environment_resolves_tasks_csv():
	with Store() as store:
		store.add(1)
		with _start_without_csv(["--host", "127.0.0.1", "--port", "0"], env={"TASKVIEW_DATA_DIR": str(store.dir)}) as server:
			xtest.contains(str(store.csv), server.startup())

def test_R1_xdg_data_home_resolves_under_taskview():
	with Store() as store:
		store.add(1)
		xdg = Path(store.dir) / "xdg"
		expected = xdg / "taskview" / "tasks.csv"
		seed_store(expected, 1)
		with _start_without_csv(["--host", "127.0.0.1", "--port", "0"], env={"XDG_DATA_HOME": str(xdg)}) as server:
			xtest.contains(str(expected), server.startup())

def test_R1_home_fallback_resolves_under_local_share():
	with Store() as store:
		home = store.dir / "home"
		expected = home / ".local" / "share" / "taskview" / "tasks.csv"
		seed_store(expected, 1)
		env = {"HOME": str(home), "XDG_DATA_HOME": None}
		with _start_without_csv(["--host", "127.0.0.1", "--port", "0"], env=env) as server:
			xtest.contains(str(expected), server.startup())

def test_R2_a_missing_store_exits_1_and_names_the_path():
	with Store() as store:
		missing = store.dir / "missing.csv"
		code, stdout, stderr = run_taskboard("--csv", missing, "--port", "0")
		xtest.equal(code, 1)
		xtest.contains(str(missing), stdout + stderr)

def test_R2_a_missing_store_is_not_created():
	with Store() as store:
		missing = store.dir / "missing.csv"
		code, stdout, stderr = run_taskboard("--csv", missing, "--port", "0")
		xtest.equal(code, 1)
		xtest.true(not missing.exists(), "a failed start must not create the store")

def test_R2_the_store_is_checked_before_the_port_is_bound():
	with Store() as store:
		missing = store.dir / "missing.csv"
		with socket.socket() as held:
			held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			held.bind(("127.0.0.1", 0))
			held.listen(1)
			port = held.getsockname()[1]
			code, stdout, stderr = run_taskboard("--csv", missing, "--port", port)
		text = stdout + stderr
		xtest.contains(str(missing), text)
		xtest.true("address already in use" not in text.lower(), "the store must be checked before the bind")

def test_R32_the_suite_is_registered_in_the_runner():
	source = (Path(ROOT) / "tools" / "run_tests.py").read_text(encoding="utf-8")
	xtest.contains("tools/taskboard/test", source)

def test_R30_help_lists_the_documented_options():
	code, stdout, stderr = run_taskboard("--help")
	text = stdout + stderr
	xtest.equal(code, 0)
	for option in ("--csv", "--data-dir", "--host", "--port", "--token"):
		xtest.contains(option, text)

def test_R13_delete_on_the_tasks_route_is_405():
	with Store() as store:
		store.add(1)
		with start_server(store) as server:
			response = request(server.base + "/api/tasks", "DELETE")
			xtest.equal(response.status, 405)
			xtest.contains("GET", response.header("Allow"))

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
