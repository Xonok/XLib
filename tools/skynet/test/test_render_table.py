"""render_table must drop a model only when it was never used.

A model can total 0 tokens and still have produced messages — a failed request,
an exhausted free pool, a 429. That is the traffic the table exists to show, so
the drop condition tests message count, not token total.
"""
import os,re,sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(ROOT))
import skynet

NOW = 1000.0

def row():
	return {
		"msgs": 0, "input": 0, "output": 0, "total": 0,
		"reasoning": 0, "cache_read": 0, "cache_write": 0,
		"refusals": 0, "last_refusal": 0,
		"finish_stop": 0, "finish_tool_calls": 0, "finish_length": 0, "finish_unknown": 0,
		"other_errors": 0, "last_other_error": 0,
		"first_seen": 0, "last_seen": 0,
	}

def stats(**kwargs):
	d = row()
	d.update(kwargs)
	return d

def rows(*models):
	"""Each argument is (name,) or (name, overrides)."""
	by_model = defaultdict(row)
	for model in models:
		name, kwargs = model[0], (model[1] if len(model) > 1 else {})
		by_model[name].update(kwargs)
	return by_model

def test_used_model_with_zero_tokens_is_rendered():
	out = skynet.render_table(rows(("free-pool", {"msgs": 2})), NOW)
	assert "free-pool" in out, "a used model with 0 tokens must be rendered: %r" % out

def test_never_used_model_is_dropped():
	out = skynet.render_table(rows(("never-used",)), NOW)
	assert "never-used" not in out, "a model with 0 messages must be dropped: %r" % out

def test_only_never_used_models_reports_no_activity():
	out = skynet.render_table(rows(("ghost-a",), ("ghost-b",)), NOW)
	assert out == "no agents active", "expected the empty message, got %r" % out

def test_zero_token_row_reports_its_message_count():
	out = skynet.render_table(rows(("free-pool", {"msgs": 7})), NOW)
	assert re.search(r"free-pool\s+7\s", out), "expected Msgs=7 in %r" % out

def test_refused_model_with_zero_tokens_is_visible():
	by_model = rows(("rate-limited", {"msgs": 3, "refusals": 3, "last_refusal": 900}))
	out = skynet.render_table(by_model, NOW)
	assert "rate-limited" in out, "a 429-only model is exactly what must show: %r" % out

def test_cap_counts_rendered_models_not_all_models():
	by_model = rows(("m1", {"msgs": 1, "total": 90}), ("m2", {"msgs": 1, "total": 80}),
					("unused-hi", {"total": 999}), ("zero-token", {"msgs": 1}))
	out = skynet.render_table(by_model, NOW, max_models=2)
	assert "m1" in out and "m2" in out, "top two by tokens should render: %r" % out

def test_empty_aggregate_reports_no_activity():
	assert skynet.render_table(defaultdict(row), NOW) == "no agents active"

def main():
	failed = 0
	for name, fn in sorted(globals().items()):
		if not name.startswith("test_") or not callable(fn):
			continue
		try:
			fn()
			print("pass %s" % name)
		except AssertionError as e:
			print("FAIL %s: %s" % (name, e))
			failed += 1
	return failed

if __name__ == "__main__":
	sys.exit(1 if main() else 0)
