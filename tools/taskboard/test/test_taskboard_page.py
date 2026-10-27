"""The served page: table, summary, editing markers and the content policy.

The repository has no DOM harness, so these tests fetch the three assets and
assert the markers the spec makes observable from their text. The editing
interaction itself is inspection, as R32 says. The requirement each test traces
to is in its name.
"""
import re,sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import xtest
from _harness import Store,get,start_server

def _assets(store):
	with start_server(store) as server:
		html = get(server, "/").body.decode("utf-8")
		script = get(server, "/board.js").body.decode("utf-8")
		style = get(server, "/board.css").body.decode("utf-8")
	return html, script, style

def _store():
	store = Store()
	store.add(1, title="one")
	return store

def _has_any(text, *needles):
	return any(needle in text for needle in needles)

def test_R15_the_page_has_a_semantic_table():
	store = _store()
	try:
		html, _, _ = _assets(store)
		xtest.contains("<table", html.lower())
		xtest.contains("<thead", html.lower())
	finally:
		store.close()

def test_R15_the_table_names_its_five_columns():
	store = _store()
	try:
		html, script, _ = _assets(store)
		text = (html + script).lower()
		for column in ("#", "due", "category", "title", "tags"):
			xtest.contains(column, text)
	finally:
		store.close()

def test_R15_the_id_column_carries_the_hash_prefix():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.contains("#", script)
	finally:
		store.close()

def test_R16_the_summary_names_the_six_counts():
	store = _store()
	try:
		html, script, _ = _assets(store)
		text = (html + script).lower()
		for count in ("open", "overdue", "today", "later", "undated"):
			xtest.contains(count, text)
		xtest.true(_has_any(text, "this week", "this_week"), "the this-week count must be shown")
	finally:
		store.close()

def test_R16_an_empty_board_says_so():
	store = _store()
	try:
		html, script, _ = _assets(store)
		xtest.contains("no open tasks", (html + script).lower())
	finally:
		store.close()

def test_R16_the_store_path_is_shown():
	store = _store()
	try:
		_, script, _ = _assets(store)
		text = script.lower()
		xtest.contains("store", text)
		xtest.contains("path", text)
	finally:
		store.close()

def test_R16_the_age_of_the_last_refresh_is_shown():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.contains("refresh", script.lower())
	finally:
		store.close()

def test_R17_the_due_cell_opens_an_input():
	store = _store()
	try:
		_, script, _ = _assets(store)
		text = script.lower()
		xtest.contains("click", text)
		xtest.contains("enter", text)
		xtest.contains("input", text)
		xtest.contains("due_date", text)
	finally:
		store.close()

def test_R17_escape_cancels_the_editor():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.contains("escape", script.lower())
	finally:
		store.close()

def test_R18_a_rejection_keeps_the_editor_and_shows_the_message():
	store = _store()
	try:
		_, script, _ = _assets(store)
		text = script.lower()
		xtest.contains("message", text)
		xtest.contains("expected_chg_ts", text)
	finally:
		store.close()

def test_R18_a_conflict_is_shown_as_a_conflict():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.contains("conflict", script.lower())
	finally:
		store.close()

def test_R19_no_asset_fetches_an_external_url():
	store = _store()
	try:
		html, script, style = _assets(store)
		text = (html + script + style).lower()
		xtest.true("http://" not in text, "an asset names an http URL")
		xtest.true("https://" not in text, "an asset names an https URL")
		xtest.true("@import" not in text, "the stylesheet imports another file")
	finally:
		store.close()

def test_R19_the_page_has_a_noscript_message():
	store = _store()
	try:
		html, _, _ = _assets(store)
		xtest.contains("<noscript", html.lower())
	finally:
		store.close()

def test_R19_the_page_does_not_fetch_a_favicon():
	store = _store()
	try:
		html, script, style = _assets(store)
		text = (html + script + style).lower()
		xtest.true("rel=\"icon\"" not in text)
		xtest.true("favicon" not in text)
	finally:
		store.close()

def test_R20_the_poll_interval_is_two_seconds():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.contains("2000", script)
	finally:
		store.close()

def test_R20_polling_pauses_while_the_tab_is_hidden():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.contains("visibilitychange", script)
		xtest.contains("hidden", script)
	finally:
		store.close()

def test_R20_a_failed_poll_shows_the_connection_banner():
	store = _store()
	try:
		html, script, _ = _assets(store)
		text = (html + script).lower()
		xtest.contains("connection lost", text)
		xtest.contains("retrying", text)
	finally:
		store.close()

def test_R21_task_text_is_inserted_as_text():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.contains("textContent", script)
	finally:
		store.close()

def test_R21_the_script_does_not_build_data_with_innerHTML():
	store = _store()
	try:
		_, script, _ = _assets(store)
		xtest.true("innerHTML" not in script, "task data must never be assigned as HTML")
	finally:
		store.close()

def test_R23_the_script_and_style_are_separate_files():
	store = _store()
	try:
		html, _, _ = _assets(store)
		text = html.lower()
		xtest.contains("board.js", text)
		xtest.contains("board.css", text)
	finally:
		store.close()

def test_R23_the_page_has_no_inline_script_or_style():
	store = _store()
	try:
		html, _, _ = _assets(store)
		text = html.lower()
		xtest.true("<style" not in text, "the page must not carry an inline stylesheet")
		xtest.true(not re.search(r"<script(?![^>]*\bsrc=)", text), "the page must not carry an inline script")
	finally:
		store.close()

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
