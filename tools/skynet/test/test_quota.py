"""The quota line: provider counters, pace math, day state and the width fallback.

Covers `tools/skynet/SPEC.md` R1–R7. No test touches the network or the real
database: credentials come from a temporary SQLite file, the state from a
temporary path, and every HTTP read from a fake `fetch`.
"""
import datetime,json,os,sqlite3,sys,tempfile
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, os.path.join(REPO, "tools"))

import xtest
import skynet

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
GO_URL = "https://opencode.ai/console/api/go/status"
OR_URL = "https://openrouter.ai/api/v1/key"
PERIOD_START = datetime.datetime(2026, 10, 1, tzinfo=UTC).isoformat()
PERIOD_END = datetime.datetime(2026, 10, 31, tzinfo=UTC).isoformat()
LIMIT = 6_000_000_000
ACCESS = "secret-access-token"
OR_KEY = "secret-openrouter-key"

def _utc(year, month, day, hour=0, minute=0):
	"""A time on the UTC day boundary the quota line measures against."""
	return datetime.datetime(year, month, day, hour, minute, tzinfo=UTC)

def _db(folder, rows):
	"""A temporary credential database; each row is (integration_id, value, active, time_updated)."""
	path = Path(folder) / "opencode.db"
	conn = sqlite3.connect(path)
	conn.execute("CREATE TABLE credential (id TEXT, integration_id TEXT, value TEXT, active INTEGER, time_updated INTEGER)")
	for integration, value, active, updated in rows:
		text = value if isinstance(value, str) else json.dumps(value)
		conn.execute(
			"INSERT INTO credential (integration_id, value, active, time_updated) VALUES (?, ?, ?, ?)",
			(integration, text, active, updated))
	conn.commit()
	conn.close()
	return str(path)

def _go_value(access=ACCESS, expires=None, server="https://opencode.ai/console"):
	"""The JSON an opencode credential row carries."""
	if expires is None:
		expires = int(NOW.timestamp() * 1000) + 3_600_000
	return {"access": access, "expires": expires, "metadata": {"server": server}}

def _or_value(key=OR_KEY):
	"""The JSON an openrouter credential row carries."""
	return {"key": key, "type": "api"}

def _go_response(product="go", used=300_000_000, limit=LIMIT, start=PERIOD_START, end=PERIOD_END):
	"""A Go status response with the month meter filled in."""
	return {
		"product": product,
		"access": {
			"startsAt": start,
			"endsAt": end,
			"meters": {"month": {"limitMicroCents": str(limit), "usedMicroCents": str(used)}},
		},
	}

def _or_response(used=29, limit=1000):
	"""An OpenRouter key response with the free-model counter filled in."""
	return {"data": {"free_model_daily_requests": {"used": used, "limit": limit, "remaining": limit - used}}}

class _Fetch:
	"""A fake HTTP layer that records the URL and headers it was given."""

	def __init__(self, responses):
		self.responses = responses
		self.calls = []

	def __call__(self, url, headers):
		self.calls.append((url, dict(headers)))
		response = self.responses[url]
		if isinstance(response, Exception):
			raise response
		return response

def _ok_go(used=300_000_000, limit=LIMIT, product="go", start=PERIOD_START, end=PERIOD_END):
	return {
		"state": "ok",
		"product": product,
		"start": skynet._parse_time(start),
		"end": skynet._parse_time(end),
		"period_start": start,
		"limit": limit,
		"used": used,
	}

def _aligned(block, width):
	"""The acceptance line at `width`: the block against the right edge."""
	title = "=== Skynet ==="
	return title + " " * (width - len(title) - len(block)) + block

def _display_quota(go=None, openrouter=None, percent=3, overall=72, today=94):
	"""The sample a renderer sees, with the numbers the SPEC's acceptance table uses."""
	if go is None:
		go = _ok_go(used=187_000_000)
	if openrouter is None:
		openrouter = {"state": "ok", "used": 29, "limit": 1000}
	return {
		"go": go,
		"openrouter": openrouter,
		"pace": {"used_percent": percent, "overall": overall, "today": today},
	}

# --- credentials -----------------------------------------------------------

def test_the_go_credential_is_the_active_row():
	with tempfile.TemporaryDirectory() as folder:
		path = _db(folder, [
			("opencode", _go_value(access="old"), 0, 10),
			("opencode", _go_value(access="new"), 1, 20),
		])
		go = skynet.read_credentials(path)["go"]
	xtest.equal(go["state"], "ok", "the active row is the credential")
	xtest.equal(go["access"], "new", "the inactive row is not used")

def test_a_missing_go_row_is_absent():
	with tempfile.TemporaryDirectory() as folder:
		path = _db(folder, [])
		go = skynet.read_credentials(path)["go"]
	xtest.equal(go["state"], "absent", "no row means no Go subscription")

def test_malformed_go_credential_json_is_unavailable():
	with tempfile.TemporaryDirectory() as folder:
		path = _db(folder, [("opencode", "{not json", 1, 10)])
		go = skynet.read_credentials(path)["go"]
	xtest.equal(go["state"], "unavailable", "a corrupt row is configured but unreadable")

def test_openrouter_prefers_an_active_row():
	with tempfile.TemporaryDirectory() as folder:
		path = _db(folder, [
			("openrouter", _or_value("old"), 0, 10),
			("openrouter", _or_value("new"), 1, 20),
		])
		key = skynet.read_credentials(path)["openrouter"]["key"]
	xtest.equal(key, "new", "the active row wins even when it is older")

def test_openrouter_takes_the_newest_row_when_none_is_active():
	with tempfile.TemporaryDirectory() as folder:
		path = _db(folder, [
			("openrouter", _or_value("old"), 0, 10),
			("openrouter", _or_value("new"), 0, 20),
		])
		key = skynet.read_credentials(path)["openrouter"]["key"]
	xtest.equal(key, "new", "the greatest time_updated wins")

def test_a_missing_openrouter_row_is_absent():
	with tempfile.TemporaryDirectory() as folder:
		path = _db(folder, [])
		openrouter = skynet.read_credentials(path)["openrouter"]
	xtest.equal(openrouter["state"], "absent", "no row means no OpenRouter key")

# --- Go --------------------------------------------------------------------

def test_go_requests_the_status_endpoint_with_bearer_and_user_agent():
	fetch = _Fetch({GO_URL: _go_response()})
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	skynet.go_quota(credential, NOW, fetch)
	url, headers = fetch.calls[0]
	xtest.equal(url, GO_URL, "the endpoint comes from metadata.server")
	xtest.equal(headers.get("Authorization"), f"Bearer {ACCESS}", "the access token is a bearer token")
	xtest.equal(headers.get("User-Agent"), "skynet/1.0", "the explicit user agent is sent")

def test_go_parses_the_month_meter_as_integers():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: _go_response(used=300_000_000)}))
	xtest.equal((go["limit"], go["used"]), (LIMIT, 300_000_000), "microcents stay integers")

def test_the_subscription_reset_rounds_to_the_nearest_utc_midnight():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	for end, expected in (
		("2026-10-31T16:47:40.000Z", datetime.datetime(2026, 11, 1, tzinfo=UTC)),
		("2026-10-31T09:00:00.000Z", datetime.datetime(2026, 10, 31, tzinfo=UTC)),
		("2026-10-31T12:00:00.000Z", datetime.datetime(2026, 11, 1, tzinfo=UTC)),
	):
		go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: _go_response(end=end)}))
		xtest.equal(go["end"], expected, f"{end} rounds to the closer midnight")

def test_an_expired_go_token_is_unavailable_without_a_request():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) - 1, "server": "https://opencode.ai/console"}
	fetch = _Fetch({GO_URL: _go_response()})
	go = skynet.go_quota(credential, NOW, fetch)
	xtest.equal(go["state"], "unavailable", "an expired token cannot be read")
	xtest.equal(len(fetch.calls), 0, "no request is made with an expired token")

def test_a_404_makes_go_absent():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: skynet._HTTPFailure(404)}))
	xtest.equal(go["state"], "absent", "a 404 means the account has no Go product")

def test_a_null_access_makes_go_absent():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: {"product": "go", "access": None}}))
	xtest.equal(go["state"], "absent", "no access block means no subscription")

def test_a_missing_month_meter_is_unavailable():
	response = _go_response()
	del response["access"]["meters"]["month"]
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: response}))
	xtest.equal(go["state"], "unavailable", "a valid response without the meter is unreadable")

def test_an_unauthorized_go_request_is_unavailable():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: skynet._HTTPFailure(401)}))
	xtest.equal(go["state"], "unavailable", "401 leaves the field unknown")

def test_a_network_failure_is_unavailable():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: OSError("offline")}))
	xtest.equal(go["state"], "unavailable", "a failed read never raises into the renderer")

def test_malformed_go_json_is_unavailable():
	credential = {"state": "ok", "access": ACCESS, "expires": int(NOW.timestamp() * 1000) + 1000, "server": "https://opencode.ai/console"}
	go = skynet.go_quota(credential, NOW, _Fetch({GO_URL: ValueError("bad json")}))
	xtest.equal(go["state"], "unavailable", "malformed JSON is a failed read")

# --- OpenRouter ------------------------------------------------------------

def test_openrouter_parses_the_free_request_counter():
	credential = {"state": "ok", "key": OR_KEY}
	openrouter = skynet.openrouter_quota(credential, _Fetch({OR_URL: _or_response(29, 1000)}))
	xtest.equal((openrouter["used"], openrouter["limit"]), (29, 1000), "the counter is used as reported")

def test_openrouter_sends_bearer_and_user_agent():
	credential = {"state": "ok", "key": OR_KEY}
	fetch = _Fetch({OR_URL: _or_response()})
	skynet.openrouter_quota(credential, fetch)
	url, headers = fetch.calls[0]
	xtest.equal(url, OR_URL, "the key endpoint is fixed")
	xtest.equal(headers.get("Authorization"), f"Bearer {OR_KEY}", "the key is a bearer token")
	xtest.equal(headers.get("User-Agent"), "skynet/1.0", "the explicit user agent is sent")

def test_a_missing_free_request_counter_is_unavailable():
	credential = {"state": "ok", "key": OR_KEY}
	openrouter = skynet.openrouter_quota(credential, _Fetch({OR_URL: {"data": {}}}))
	xtest.equal(openrouter["state"], "unavailable", "a key without the counter is unreadable")

def test_a_missing_openrouter_key_is_absent():
	openrouter = skynet.openrouter_quota({"state": "absent"}, _Fetch({}))
	xtest.equal(openrouter["state"], "absent", "no key means no OpenRouter field")

def test_an_openrouter_http_failure_is_unavailable():
	credential = {"state": "ok", "key": OR_KEY}
	openrouter = skynet.openrouter_quota(credential, _Fetch({OR_URL: skynet._HTTPFailure(403)}))
	xtest.equal(openrouter["state"], "unavailable", "403 leaves the field unknown")

# --- pace ------------------------------------------------------------------

def test_the_sustainable_rate_is_one_hundred_percent():
	go = _ok_go(used=3_000_000_000)
	pace = skynet.compute_pace(go, None, _utc(2026, 10, 16))
	xtest.equal(round(pace["overall"]), 100, "half the period and half the quota is sustainable")

def test_twice_the_sustainable_rate_is_two_hundred_percent():
	go = _ok_go(used=6_000_000_000)
	pace = skynet.compute_pace(go, None, _utc(2026, 10, 16))
	xtest.equal(round(pace["overall"]), 200, "twice the rate exhausts the quota halfway")

def test_the_used_percentage_is_reported():
	go = _ok_go(used=1_500_000_000)
	pace = skynet.compute_pace(go, None, _utc(2026, 10, 16))
	xtest.equal(round(pace["used_percent"]), 25, "a quarter of the limit is 25%")

def test_today_is_the_share_of_the_daily_allowance():
	go = _ok_go(used=3_000_000_000)
	pace = skynet.compute_pace(go, 2_900_000_000, _utc(2026, 10, 26, 12))
	xtest.equal(round(pace["today"]), 50, "half of the day's allowance is 50%")

def test_today_does_not_depend_on_the_time_of_day():
	go = _ok_go(used=3_000_000_000)
	morning = skynet.compute_pace(go, 2_900_000_000, _utc(2026, 10, 26, 1))
	evening = skynet.compute_pace(go, 2_900_000_000, _utc(2026, 10, 26, 23))
	xtest.equal(morning["today"], evening["today"], "idle time does not dilute the day's share")

def test_today_is_unknown_without_a_baseline():
	go = _ok_go()
	pace = skynet.compute_pace(go, None, _utc(2026, 10, 26, 12))
	xtest.equal(pace["today"], None, "no baseline means no day share")

def test_today_is_unknown_when_the_meter_fell():
	go = _ok_go(used=100_000_000)
	pace = skynet.compute_pace(go, 200_000_000, _utc(2026, 10, 26, 12))
	xtest.equal(pace["today"], None, "a meter that fell cannot give a day share")

def test_pace_is_unknown_before_the_period_starts():
	go = _ok_go()
	pace = skynet.compute_pace(go, None, _utc(2026, 9, 30))
	xtest.equal(pace["overall"], None, "elapsed time is not positive")

def test_pace_is_unknown_with_a_zero_limit():
	go = _ok_go(limit=0)
	pace = skynet.compute_pace(go, None, _utc(2026, 10, 16))
	xtest.equal(pace["overall"], None, "a zero limit has no sustainable rate")
	xtest.equal(pace["used_percent"], None, "a zero limit has no percentage")

# --- day state -------------------------------------------------------------

def _state(day, day_start_used=None, last_used=1_000, last_seen=0, period_start=PERIOD_START):
	return {
		"version": 1,
		"go": {
			"day": day,
			"day_start_used": day_start_used,
			"last_used": last_used,
			"last_seen": last_seen,
			"period_start": period_start,
		},
	}

def _save(path, state):
	with open(path, "w", encoding="utf-8") as file:
		json.dump(state, file)

def _load(path):
	with open(path, encoding="utf-8") as file:
		return json.load(file)

def test_a_first_read_sets_the_baseline_to_the_current_meter():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		baseline = skynet.update_day_state(path, _ok_go(used=123_000_000), _utc(2026, 10, 26, 10))
		state = _load(path)["go"]
	xtest.equal(baseline, 123_000_000, "the first reading of the day starts today at zero")
	xtest.equal(state["day_start_used"], 123_000_000, "the baseline is persisted")
	xtest.equal(state["last_used"], 123_000_000, "the meter is recorded for the next read")
	xtest.equal(state["day"], "2026-10-26", "the UTC day is recorded")

def test_the_state_day_is_the_utc_date():
	tz = datetime.timezone(datetime.timedelta(hours=2))
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		now = datetime.datetime(2026, 10, 26, 0, 30, tzinfo=tz)
		skynet.update_day_state(path, _ok_go(used=123_000_000), now)
		state = _load(path)["go"]
	xtest.equal(state["day"], "2026-10-25", "the state day is the UTC date, not the local one")

def test_the_baseline_is_kept_within_the_same_day():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		_save(path, _state("2026-10-26", day_start_used=111, last_seen=int(_utc(2026, 10, 26, 1).timestamp())))
		baseline = skynet.update_day_state(path, _ok_go(used=222_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 111, "an existing baseline is not replaced")

def test_the_first_read_of_a_new_day_starts_today_at_the_current_meter():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		_save(path, _state("2026-10-25", last_used=500_000_000, last_seen=int(_utc(2026, 10, 25, 18).timestamp())))
		baseline = skynet.update_day_state(path, _ok_go(used=600_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 600_000_000, "usage before the first read counts as the previous day")

def test_a_null_baseline_for_today_is_filled_from_the_current_meter():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		_save(path, _state("2026-10-26", day_start_used=None, last_used=500_000_000, last_seen=int(_utc(2026, 10, 26, 1).timestamp())))
		baseline = skynet.update_day_state(path, _ok_go(used=600_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 600_000_000, "the cold-start day gets a baseline on the next read")

def test_a_changed_period_continues_the_day_across_the_new_meter():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		_save(path, _state("2026-10-26", day_start_used=100_000_000, last_used=150_000_000, last_seen=int(_utc(2026, 10, 26, 1).timestamp()), period_start="2026-09-01T00:00:00.000Z"))
		baseline = skynet.update_day_state(path, _ok_go(used=1_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, -50_000_000, "the pre-reset day spend is carried across the reset")

def test_a_changed_period_on_a_new_day_starts_at_the_current_meter():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		_save(path, _state("2026-10-25", day_start_used=100_000_000, last_used=150_000_000, last_seen=int(_utc(2026, 10, 25, 23).timestamp()), period_start="2026-09-01T00:00:00.000Z"))
		baseline = skynet.update_day_state(path, _ok_go(used=1_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 1_000_000, "a new day starts today at the current meter")

def test_a_decreasing_meter_starts_today_at_the_current_meter():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		_save(path, _state("2026-10-26", day_start_used=111, last_used=500_000_000, last_seen=int(_utc(2026, 10, 26, 1).timestamp())))
		baseline = skynet.update_day_state(path, _ok_go(used=100_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 100_000_000, "a meter that went down restarts today at the current reading")

def test_a_corrupt_state_file_still_gets_a_baseline():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		path.write_text("{not json", encoding="utf-8")
		baseline = skynet.update_day_state(path, _ok_go(used=123_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 123_000_000, "a corrupt file behaves like no file and uses the current meter")

def test_a_state_with_wrong_types_still_gets_a_baseline():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		_save(path, {"version": 1, "go": {"day": 123, "day_start_used": "x", "last_used": "y", "last_seen": [], "period_start": 42}})
		baseline = skynet.update_day_state(path, _ok_go(used=123_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 123_000_000, "a value of the wrong type cannot stop the baseline")

def test_a_write_failure_still_returns_the_baseline():
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "quota.json"
		path.mkdir()
		baseline = skynet.update_day_state(path, _ok_go(used=123_000_000), _utc(2026, 10, 26, 10))
	xtest.equal(baseline, 123_000_000, "an unwritable state file must not hide today's pace")

# --- display ---------------------------------------------------------------

def test_the_full_line_carries_every_field():
	line = skynet.quota_line(_display_quota(), 70)
	xtest.equal(line, _aligned("Go $1.87/$60 3% · pace 72%/d · today 94% · OR 29/1000", 70), "the acceptance table's full line")

def test_the_line_abbreviates_before_dropping():
	line = skynet.quota_line(_display_quota(), 60)
	xtest.equal(line, _aligned("G $1.87/60 3% · p 72 · t 94 · OR 29/1000", 60), "the abbreviated form keeps every field")

def test_the_openrouter_field_drops_first():
	line = skynet.quota_line(_display_quota(), 50)
	xtest.equal(line, _aligned("G $1.87/60 3% · p 72 · t 94", 50), "OR goes before today")

def test_the_today_field_drops_next():
	line = skynet.quota_line(_display_quota(), 40)
	xtest.equal(line, _aligned("G $1.87/60 3% · p 72", 40), "today goes before pace")

def test_the_pace_field_drops_next():
	line = skynet.quota_line(_display_quota(), 34)
	xtest.equal(line, _aligned("G $1.87/60 3%", 34), "pace goes before the Go field is shortened")

def test_the_go_limit_drops_before_the_percentage():
	line = skynet.quota_line(_display_quota(), 27)
	xtest.equal(line, _aligned("G $1.87 3%", 27), "the limit goes first")

def test_the_go_field_keeps_only_the_percentage_at_the_narrowest():
	line = skynet.quota_line(_display_quota(), 22)
	xtest.equal(line, _aligned("G 3%", 22), "only the percentage remains")

def test_the_title_alone_fits_a_very_narrow_pane():
	line = skynet.quota_line(_display_quota(), 15)
	xtest.equal(line, "=== Skynet ===", "the title is the last field to survive")

def test_an_unavailable_go_shows_a_question_mark_and_no_pace():
	quota = _display_quota(go={"state": "unavailable"}, overall=None, today=None)
	line = skynet.quota_line(quota, 80)
	xtest.equal(line, _aligned("Go ? · OR 29/1000", 80), "a configured but unreadable source is a question mark")

def test_an_unavailable_openrouter_shows_a_question_mark():
	quota = _display_quota(openrouter={"state": "unavailable"})
	line = skynet.quota_line(quota, 80)
	xtest.equal(line, _aligned("Go $1.87/$60 3% · pace 72%/d · today 94% · OR ?", 80), "the counter is unknown, not absent")

def test_absent_sources_contribute_nothing():
	quota = {"go": {"state": "absent"}, "openrouter": {"state": "absent"}, "pace": {"used_percent": None, "overall": None, "today": None}}
	line = skynet.quota_line(quota, 80)
	xtest.equal(line, "=== Skynet ===", "nothing configured, nothing shown")

def test_go_plus_is_labelled_go_plus():
	quota = _display_quota(go=_ok_go(used=187_000_000, product="go-plus"))
	line = skynet.quota_line(quota, 80)
	xtest.contains("Go+ $1.87/$60 3%", line, "the plus product is not called Go")

def test_the_quota_block_is_pushed_to_the_right_edge():
	quota = _display_quota()
	for width in (70, 80, 120):
		line = skynet.quota_line(quota, width)
		xtest.equal(len(line), width, f"the block fills width {width}")
		xtest.true(line.endswith("OR 29/1000"), "the block ends at the right edge")

def test_a_fallback_block_stays_at_the_right_edge():
	for width, suffix in ((50, "t 94"), (34, "G $1.87/60 3%"), (22, "G 3%")):
		line = skynet.quota_line(_display_quota(), width)
		xtest.equal(len(line), width, f"the fallback fills width {width}")
		xtest.true(line.endswith(suffix), f"width {width} ends with {suffix}")

def test_the_quota_line_never_exceeds_the_width():
	quota = _display_quota()
	for width in range(14, 121):
		line = skynet.quota_line(quota, width)
		xtest.true(len(line) <= width, f"width {width} cannot carry {len(line)} columns")
		xtest.true("\n" not in line, f"width {width} stayed on one line")
		if width >= 19:
			xtest.equal(len(line), width, f"width {width} keeps the block at its edge")

def test_render_puts_the_quota_line_first_and_keeps_the_tables():
	rows = [("model-a", datetime.datetime.now().timestamp(), 100, 100, 1000, 0, 0, 0, None, None, "stop", "session")]
	out = skynet.render(rows, datetime.datetime.now().timestamp(), height=24, width=120, quota=_display_quota())
	lines = out.splitlines()
	xtest.true(lines[0].startswith("=== Skynet ==="), "the quota rides on the first line")
	xtest.true(lines[0].endswith("OR 29/1000"), "the block ends at the right edge")
	xtest.contains("=== Models (Today) ===", out, "the tables are unchanged")

def test_render_without_quota_keeps_the_old_header():
	rows = [("model-a", datetime.datetime.now().timestamp(), 100, 100, 1000, 0, 0, 0, None, None, "stop", "session")]
	out = skynet.render(rows, datetime.datetime.now().timestamp(), height=24, width=120)
	xtest.equal(out.splitlines()[0], "=== Skynet ===", "no quota means the old header")

# --- sampling --------------------------------------------------------------

def test_sample_quota_reads_both_sources_and_writes_the_state():
	with tempfile.TemporaryDirectory() as folder:
		db = _db(folder, [
			("opencode", _go_value(), 1, 10),
			("openrouter", _or_value(), 0, 20),
		])
		state = Path(folder) / "quota.json"
		fetch = _Fetch({GO_URL: _go_response(), OR_URL: _or_response()})
		quota = skynet.sample_quota(now=NOW, state_path=state, fetch=fetch, db_path=db)
		xtest.equal((quota["go"]["state"], quota["openrouter"]["state"]), ("ok", "ok"), "both sources were read")
		xtest.true(state.exists(), "a successful Go read writes the day state")

def test_sample_quota_still_reports_openrouter_when_go_fails():
	with tempfile.TemporaryDirectory() as folder:
		db = _db(folder, [
			("opencode", _go_value(), 1, 10),
			("openrouter", _or_value(), 0, 20),
		])
		fetch = _Fetch({GO_URL: skynet._HTTPFailure(500), OR_URL: _or_response()})
		quota = skynet.sample_quota(now=NOW, state_path=Path(folder) / "quota.json", fetch=fetch, db_path=db)
		line = skynet.quota_line(quota, 80)
	xtest.equal(quota["go"]["state"], "unavailable", "the Go failure is isolated")
	xtest.contains("OR 29/1000", line, "OpenRouter still renders")

def test_sample_quota_with_no_credentials_is_empty():
	with tempfile.TemporaryDirectory() as folder:
		db = _db(folder, [])
		fetch = _Fetch({})
		quota = skynet.sample_quota(now=NOW, state_path=Path(folder) / "quota.json", fetch=fetch, db_path=db)
		line = skynet.quota_line(quota, 80)
	xtest.equal(line, "=== Skynet ===", "nothing configured, nothing shown")

# --- HTTP ------------------------------------------------------------------

def test_the_http_request_sets_the_user_agent():
	class _Response:
		def __enter__(self):
			return self

		def __exit__(self, *args):
			return False

		def read(self):
			return b'{"ok": true}'

	captured = {}

	def fake_urlopen(request, timeout):
		captured["request"] = request
		captured["timeout"] = timeout
		return _Response()

	saved = skynet.urllib.request.urlopen
	skynet.urllib.request.urlopen = fake_urlopen
	try:
		data = skynet.http_get_json("https://example.invalid/", {"Authorization": "Bearer x"})
	finally:
		skynet.urllib.request.urlopen = saved
	xtest.equal(data, {"ok": True}, "the body is parsed")
	xtest.equal(captured["request"].get_header("User-agent"), "skynet/1.0", "the default Python user agent is replaced")
	xtest.equal(captured["timeout"], 3, "the timeout is three seconds")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
