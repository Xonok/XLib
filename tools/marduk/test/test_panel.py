"""The panel's two sections, its feeds line and the room it has."""
import io,json,os,sys,tempfile
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event,panel,render,store
from tools.marduk._.sources import site

class Source:
	def __init__(self, id="site", keys=None, interval=60.0, stale_after=180.0):
		self.id = id
		self._keys = keys or []
		self._interval = interval
		self._stale = stale_after
	def interval(self):
		return self._interval
	def stale_after(self):
		return self._stale
	def keys(self):
		return list(self._keys)
	def check(self, now):
		return []

def _source(keys=None, id="site", interval=60.0, stale_after=180.0):
	return Source(id, keys, interval, stale_after)

def _sites():
	return _source([("site:a", "a"), ("site:b", "b")])

def _condition(state, key="site:a", source="site", name="a", kind="health", checked=1000.0, since=None):
	return event.Condition(source, key, kind, name, state, f"{name} is {state}",
		f"HTTP 200 ({0.1:.1f}s)", since=checked if since is None else since, checked=checked)

def _snapshot(conditions=None, news=None, sources=None):
	return {"conditions": conditions or [], "news": news or [], "sources": sources or {}}

def _render(sources, snapshot, height=20, width=80, now=1000.0, notices=None):
	return render.render(sources, snapshot, now, height, width, False, notices)

def _text(lines):
	return "\n".join(render._ANSI.sub("", line) for line in lines)

def _write_config(folder, data):
	path = os.path.join(folder, "config.json")
	with open(path, "w", encoding="utf-8") as file:
		json.dump(data, file)
	return path

def test_the_health_list_always_shows_every_configured_target():
	lines = _render([_sites()], _snapshot(sources={"site": {"last_run": 1000.0, "last_ok": 1000.0}}))
	text = _text(lines)
	xtest.contains("a", text, "the first target is listed")
	xtest.contains("b", text, "the second target is listed")
	xtest.contains("waiting for the first check", text, "an unchecked target says so")

def test_a_target_with_no_condition_shows_a_question_mark():
	lines = _render([_sites()], _snapshot(sources={"site": {"last_run": 1000.0, "last_ok": 1000.0}}))
	xtest.contains("?", _text(lines), "an unchecked target is a question mark")

def test_a_stale_source_marks_its_condition():
	snapshot = _snapshot(
		conditions=[_condition(event.STATE_ALERT, checked=700.0)],
		sources={"site": {"last_run": 700.0, "last_ok": 700.0, "last_error": ""}})
	lines = _render([_sites()], snapshot)
	text = _text(lines)
	xtest.contains("?", text, "a stale condition is a question mark")
	xtest.contains("last alert", text, "the last known state is named")

def test_the_health_age_is_the_time_in_the_state():
	snapshot = _snapshot(
		conditions=[_condition(event.STATE_ALERT, checked=1000.0, since=700.0)],
		sources={"site": {"last_run": 1000.0, "last_ok": 1000.0, "last_error": ""}})
	lines = _render([_sites()], snapshot, now=1000.0)
	xtest.contains("5m", _text(lines), "five minutes in the alert state")

def test_a_health_condition_from_another_source_is_shown():
	other = _source([], id="fake")
	condition = _condition(event.STATE_WARN, key="fake:x", source="fake", name="x")
	lines = _render([_sites(), other], _snapshot(
		conditions=[condition],
		sources={"site": {"last_run": 1000.0, "last_ok": 1000.0},
			"fake": {"last_run": 1000.0, "last_ok": 1000.0}}))
	text = _text(lines)
	xtest.contains("x", text, "a discovered health key is shown")
	xtest.contains("warn", text, "its state is shown")

def test_a_condition_whose_source_is_not_configured_is_marked():
	condition = _condition(event.STATE_ALERT, key="gone:x", source="gone", name="x")
	text = _text(_render([], _snapshot(conditions=[condition])))
	xtest.contains("not configured", text, "the missing source is named")

def test_the_feeds_line_shows_each_source():
	lines = _render([_sites(), _source([], id="fake")],
		_snapshot(sources={"site": {"last_run": 1000.0, "last_ok": 1000.0}}))
	text = _text(lines)
	xtest.contains("feeds: site", text, "the first source is on the liveness line")
	xtest.contains("fake", text, "the second source is on the liveness line")

def test_a_name_shared_by_two_instances_is_qualified():
	public = _source([("public:a", "a")], id="public")
	private = _source([("private:a", "a")], id="private")
	text = _text(_render([public, private], _snapshot()))
	xtest.contains("public/a", text, "the first instance is named")
	xtest.contains("private/a", text, "the second instance is named")

def test_a_unique_name_is_not_qualified():
	text = _text(_render([_sites()], _snapshot()))
	xtest.true("site/a" not in text, "a unique name is shown bare")

def test_no_sources_configured_is_visible():
	text = _text(_render([], _snapshot()))
	xtest.contains("feeds: (none)", text, "an empty feed list is explicit")
	xtest.contains("no checks configured", text, "an empty health list is explicit")

def test_the_news_section_says_nothing_yet():
	lines = _render([_sites()], _snapshot())
	xtest.contains("nothing yet", _text(lines), "an empty news section is explicit")

def test_the_news_section_shows_transitions():
	snapshot = _snapshot(news=[{"at": 1000.0, "title": "a is down", "detail": "HTTP 503"}])
	lines = _render([_sites()], snapshot)
	xtest.contains("a is down", _text(lines), "the transition is shown")
	xtest.contains("HTTP 503", _text(lines), "its detail is shown")

def test_the_render_fits_the_height():
	for height in range(2, 31):
		lines = _render([_sites()], _snapshot(news=[{"at": 1000.0, "title": "x", "detail": "y"}] * 10), height=height)
		xtest.true(len(lines) <= height, f"{height} rows hold at most {height}, got {len(lines)}")
		xtest.true(lines[0].endswith("=== Marduk ==="), f"the title survives {height} rows")

def test_the_render_fits_the_width():
	sources = [_source([("site:a-rather-long-site-name", "a-rather-long-site-name")])]
	for width in (30, 40, 60, 80):
		lines = _render(sources, _snapshot(news=[{"at": 1000.0, "title": "x" * 100, "detail": "y" * 100}]),
			width=width)
		xtest.true(all(render.visible_len(line) <= width for line in lines),
			f"a display of {width} columns must not run past {width}")

def test_the_compact_layout_below_46_columns():
	lines = _render([_sites()], _snapshot(), width=40)
	health = [line for line in lines if line.startswith(" a")]
	xtest.true(health, "the compact row starts with one space")

def test_a_config_error_is_visible():
	lines = _render([], _snapshot(), notices=["no config at /tmp/x"])
	xtest.contains("! no config", _text(lines), "the config error is on screen")

def test_a_store_error_is_visible():
	lines = _render([], _snapshot(), notices=["corrupt state"])
	xtest.contains("! corrupt state", _text(lines), "the store error is on screen")

def test_the_overflow_note_counts_what_was_hidden():
	news = [{"at": 1000.0 + index, "title": f"event {index}", "detail": ""} for index in range(30)]
	lines = _render([_sites()], _snapshot(news=news), height=12)
	text = _text(lines)
	xtest.true("… +" in text, "a capped list says what it left out")
	xtest.true(len(lines) <= 12, "the frame still fits")

def _fake_opener(status):
	class Response:
		def __init__(self):
			self.status = status
		def __enter__(self):
			return self
		def __exit__(self, *args):
			return False
	def open_url(url, timeout=None):
		return Response()
	return open_url

def test_run_once_checks_and_saves():
	with tempfile.TemporaryDirectory() as folder:
		config_path = _write_config(folder, {"sources": [{"kind": "site",
			"targets": [{"name": "a", "url": "https://a/"}]}]})
		state_path = os.path.join(folder, "state.json")
		original = site.OPENER
		site.OPENER = _fake_opener(200)
		try:
			with redirect_stdout(io.StringIO()):
				panel.Panel(config_path=config_path, state_path=state_path).run_once()
		finally:
			site.OPENER = original
		state = store.Store(state_path)
		state.load()
		xtest.equal(len(state.conditions), 1, "the check reached the store")
		xtest.equal(state.conditions["site:a"].state, event.STATE_OK, "the site is ok")
		xtest.equal(state.sources["site"]["last_error"], "", "the run is recorded as a success")

def test_an_unknown_source_is_a_notice_and_the_rest_run():
	with tempfile.TemporaryDirectory() as folder:
		config_path = _write_config(folder, {"sources": [
			{"kind": "site", "targets": [{"name": "a", "url": "https://a/"}]},
			{"kind": "nope"}]})
		app = panel.Panel(config_path=config_path, state_path=os.path.join(folder, "state.json"))
		xtest.equal(len(app.sources), 1, "the known source is built")
		xtest.contains("unknown source: nope", _text(app.render_lines(height=20, width=80)),
			"the unknown kind is on screen")

def test_a_malformed_source_option_is_a_notice():
	with tempfile.TemporaryDirectory() as folder:
		config_path = _write_config(folder, {"sources": [
			{"kind": "site", "targets": 5}]})
		app = panel.Panel(config_path=config_path, state_path=os.path.join(folder, "state.json"))
		xtest.equal(len(app.sources), 0, "the malformed source is not built")
		xtest.contains("site: targets must be a list", _text(app.render_lines(height=20, width=80)),
			"the bad option is on screen")

def test_a_missing_config_leaves_no_sources():
	with tempfile.TemporaryDirectory() as folder:
		app = panel.Panel(config_path=os.path.join(folder, "absent.json"),
			state_path=os.path.join(folder, "state.json"))
		xtest.equal(app.sources, [], "no config means no sources")
		xtest.contains("no config at", _text(app.render_lines(height=20, width=80)),
			"the missing config is on screen")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
