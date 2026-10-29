"""The panel's two sections, its feeds line and the room it has."""
import io,json,os,sys,tempfile,time
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event,panel,render,store
from tools.marduk._.sources import site

class Config:
	def __init__(self, sites=None, error="", site_interval=60.0):
		self.sites = sites if sites is not None else [
			{"name": "a", "url": "https://a/"},
			{"name": "b", "url": "https://b/"},
		]
		self.error = error
		self.site_interval = site_interval
		self.site_timeout = 5.0
		self.news_retention_days = 7.0

def _condition(state, key="site:a", name="a", checked=1000.0):
	return event.Condition("site", key, "health", name, state, f"{name} is {state}",
		f"HTTP 200 ({0.1:.1f}s)", checked=checked)

def _snapshot(conditions=None, news=None, sources=None):
	return {"conditions": conditions or [], "news": news or [], "sources": sources or {}}

def _render(config, snapshot, height=20, width=80, now=1000.0, notices=None):
	return render.render(config, [site], snapshot, now, height, width, False, notices)

def _text(lines):
	return "\n".join(render._ANSI.sub("", line) for line in lines)

def test_the_health_list_always_shows_every_configured_site():
	lines = _render(Config(), _snapshot(sources={"site": {"last_run": 1000.0, "last_ok": 1000.0}}))
	text = _text(lines)
	xtest.contains("a", text, "the first site is listed")
	xtest.contains("b", text, "the second site is listed")
	xtest.contains("waiting for the first check", text, "an unchecked site says so")

def test_a_site_with_no_condition_shows_a_question_mark():
	lines = _render(Config(), _snapshot(sources={"site": {"last_run": 1000.0, "last_ok": 1000.0}}))
	xtest.contains("?", _text(lines), "an unchecked site is a question mark")

def test_a_stale_source_marks_its_condition():
	snapshot = _snapshot(
		conditions=[_condition(event.STATE_ALERT, checked=700.0)],
		sources={"site": {"last_run": 700.0, "last_ok": 700.0, "last_error": ""}})
	lines = _render(Config(site_interval=60.0), snapshot)
	text = _text(lines)
	xtest.contains("?", text, "a stale condition is a question mark")
	xtest.contains("last alert", text, "the last known state is named")

def test_the_feeds_line_shows_each_source():
	lines = _render(Config(), _snapshot(sources={"site": {"last_run": 1000.0, "last_ok": 1000.0}}))
	xtest.contains("feeds: site", _text(lines), "the source is on the liveness line")

def test_the_news_section_says_nothing_yet():
	lines = _render(Config(), _snapshot())
	xtest.contains("nothing yet", _text(lines), "an empty news section is explicit")

def test_the_news_section_shows_transitions():
	snapshot = _snapshot(news=[{"at": 1000.0, "title": "a is down", "detail": "HTTP 503"}])
	lines = _render(Config(), snapshot)
	xtest.contains("a is down", _text(lines), "the transition is shown")
	xtest.contains("HTTP 503", _text(lines), "its detail is shown")

def test_the_render_fits_the_height():
	for height in range(2, 31):
		lines = _render(Config(), _snapshot(news=[{"at": 1000.0, "title": "x", "detail": "y"}] * 10), height=height)
		xtest.true(len(lines) <= height, f"{height} rows hold at most {height}, got {len(lines)}")
		xtest.true(lines[0].endswith("=== Marduk ==="), f"the title survives {height} rows")

def test_the_render_fits_the_width():
	config = Config(sites=[{"name": "a-rather-long-site-name", "url": "https://a/"}])
	for width in (30, 40, 60, 80):
		lines = _render(config, _snapshot(news=[{"at": 1000.0, "title": "x" * 100, "detail": "y" * 100}]),
			width=width)
		xtest.true(all(render.visible_len(line) <= width for line in lines),
			f"a display of {width} columns must not run past {width}")

def test_the_compact_layout_below_46_columns():
	lines = _render(Config(), _snapshot(), width=40)
	health = [line for line in lines if line.startswith(" a")]
	xtest.true(health, "the compact row starts with one space")

def test_a_config_error_is_visible():
	lines = _render(Config(error="no config at /tmp/x"), _snapshot(), notices=["no config at /tmp/x"])
	xtest.contains("! no config", _text(lines), "the config error is on screen")

def test_a_store_error_is_visible():
	lines = _render(Config(), _snapshot(), notices=["corrupt state"])
	xtest.contains("! corrupt state", _text(lines), "the store error is on screen")

def test_the_overflow_note_counts_what_was_hidden():
	news = [{"at": 1000.0 + index, "title": f"event {index}", "detail": ""} for index in range(30)]
	lines = _render(Config(), _snapshot(news=news), height=12)
	text = _text(lines)
	xtest.true("… +" in text, "a capped list says what it left out")
	xtest.true(len(lines) <= 12, "the frame still fits")

def test_run_once_checks_and_saves():
	with tempfile.TemporaryDirectory() as folder:
		config_path = os.path.join(folder, "config.json")
		state_path = os.path.join(folder, "state.json")
		with open(config_path, "w", encoding="utf-8") as file:
			json.dump({"sites": [{"name": "a", "url": "https://a/"}]}, file)
		original = site.OPENER
		def open_url(url, timeout=None):
			class Response:
				status = 200
				def __enter__(self):
					return self
				def __exit__(self, *args):
					return False
			return Response()
		site.OPENER = open_url
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

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
