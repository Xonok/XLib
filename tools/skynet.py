#!/usr/bin/env python3
"""Keep an eye on the AI agents: per-model usage, refusals, and finish reasons.

Reads opencode's message log read-only (no API calls, so this never adds usage)
and prints per-model stats including messages, tokens, refusals, and finish reasons.
"""
import argparse,datetime,os,sqlite3,sys,time
from collections import defaultdict

NAME = "Skynet"
DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
_CLEAR_SCREEN = "\033[2J\033[H"
_POLL_SECONDS = 1.0

def load_stats(limit_seconds):
	conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
	cutoff = (time.time() - limit_seconds) * 1000
	rows = conn.execute(
		"""
		SELECT json_extract(data, '$.modelID'),
			time_created/1000.0,
			json_extract(data, '$.tokens.input'),
			json_extract(data, '$.tokens.output'),
			json_extract(data, '$.tokens.total'),
			json_extract(data, '$.tokens.reasoning'),
			json_extract(data, '$.tokens.cache.read'),
			json_extract(data, '$.tokens.cache.write'),
			json_extract(data, '$.error.data.statusCode'),
			json_extract(data, '$.error.name'),
			json_extract(data, '$.finish'),
			session_id
		FROM message
		WHERE json_extract(data, '$.role') = 'assistant' AND json_extract(data, '$.time.created') >= ?
		ORDER BY time_created
		""",
		(cutoff,),
	).fetchall()
	conn.close()
	return rows

def human_age(seconds):
	if seconds < 0:
		return "now"
	minutes = int(seconds // 60)
	if minutes < 60:
		return f"{minutes}m" if minutes else "now"
	hours = minutes // 60
	if hours < 24:
		return f"{hours}h{minutes % 60:02d}m"
	days = hours // 24
	return f"{days}d{hours % 24}h"

def human_tokens(n):
	if n is None:
		return "?"
	n = int(n)
	if n >= 1000000:
		return f"{n / 1000000:.1f}M"
	if n >= 1000:
		return f"{n / 1000:.0f}k"
	return str(n)

def aggregate(rows, now):
	by_model = defaultdict(lambda: {
		"msgs": 0, "input": 0, "output": 0, "total": 0,
		"reasoning": 0, "cache_read": 0, "cache_write": 0,
		"refusals": 0, "last_refusal": 0,
		"finish_stop": 0, "finish_tool_calls": 0, "finish_length": 0, "finish_unknown": 0,
		"other_errors": 0, "last_other_error": 0,
		"first_seen": now, "last_seen": 0,
	})
	for (model, created, token_in, token_out, token_total,
		 token_reasoning, cache_read, cache_write,
		 status, error_name, finish, session_id) in rows:
		stats = by_model[model]
		stats["msgs"] += 1
		if token_in is not None:
			stats["input"] += int(token_in)
		if token_out is not None:
			stats["output"] += int(token_out)
		if token_total is not None:
			stats["total"] += int(token_total)
		if token_reasoning is not None:
			stats["reasoning"] += int(token_reasoning)
		if cache_read is not None:
			stats["cache_read"] += int(cache_read)
		if cache_write is not None:
			stats["cache_write"] += int(cache_write)
		stats["first_seen"] = min(stats["first_seen"], created)
		stats["last_seen"] = max(stats["last_seen"], created)

		if status == 429 or error_name == "MessageAbortedError":
			stats["refusals"] += 1
			stats["last_refusal"] = max(stats["last_refusal"], created)
		elif error_name and error_name not in ("MessageAbortedError",):
			stats["other_errors"] += 1
			stats["last_other_error"] = max(stats["last_other_error"], created)

		if finish == "stop":
			stats["finish_stop"] += 1
		elif finish == "tool-calls":
			stats["finish_tool_calls"] += 1
		elif finish == "length":
			stats["finish_length"] += 1
		elif finish == "unknown":
			stats["finish_unknown"] += 1
	return by_model

def render_table(by_model, now, show_tokens=True, col_w=None):
	if not by_model:
		return "no agents active"
	models = sorted(by_model, key=lambda m: -by_model[m]["total"])
	if col_w is None:
		col_w = max(len(m) for m in models)
	ref_w = 12
	if show_tokens:
		hdr = f"{'Model':<{col_w}}  {'Msgs':>5}  {'In':>7}  {'Out':>7}  {'Tot':>7}  {'Ref':>{ref_w}}  {'Len':>4}  {'Tool':>4}  {'Stop':>4}  {'Unk':>4}  {'Active'}"
		sep = f"{'─' * col_w}  {'─' * 5}  {'─' * 7}  {'─' * 7}  {'─' * 7}  {'─' * ref_w}  {'─' * 4}  {'─' * 4}  {'─' * 4}  {'─' * 4}  {'─' * 11}"
	else:
		hdr = f"{'Model':<{col_w}}  {'Msgs':>5}  {'Ref':>{ref_w}}  {'Len':>4}  {'Tool':>4}  {'Stop':>4}  {'Unk':>4}  {'Active'}"
		sep = f"{'─' * col_w}  {'─' * 5}  {'─' * ref_w}  {'─' * 4}  {'─' * 4}  {'─' * 4}  {'─' * 4}  {'─' * 11}"
	lines = [hdr, sep]
	for model in models:
		s = by_model[model]
		ref = str(s["refusals"])
		if s["last_refusal"]:
			ref += f"({human_age(now - s['last_refusal'])})"
		active = ""
		if s["last_seen"]:
			active = f"{human_age(now - s['first_seen'])}-{human_age(now - s['last_seen'])}"
		if show_tokens:
			lines.append(
				f"{model:<{col_w}}"
				f"  {s['msgs']:>5}"
				f"  {human_tokens(s['input']):>7}"
				f"  {human_tokens(s['output']):>7}"
				f"  {human_tokens(s['total']):>7}"
				f"  {ref:>{ref_w}}"
				f"  {s['finish_length']:>4}"
				f"  {s['finish_tool_calls']:>4}"
				f"  {s['finish_stop']:>4}"
				f"  {s['finish_unknown']:>4}"
				f"  {active}"
			)
		else:
			lines.append(
				f"{model:<{col_w}}"
				f"  {s['msgs']:>5}"
				f"  {ref:>{ref_w}}"
				f"  {s['finish_length']:>4}"
				f"  {s['finish_tool_calls']:>4}"
				f"  {s['finish_stop']:>4}"
				f"  {s['finish_unknown']:>4}"
				f"  {active}"
			)
	return "\n".join(lines)

def render(rows, now):
	all_stats = aggregate(rows, now)
	local_midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
	today_cutoff = local_midnight.timestamp()
	today_rows = [(m, c, ti, to, tt, tr, cr, cw, s, en, f, sid)
	              for m, c, ti, to, tt, tr, cr, cw, s, en, f, sid in rows if c >= today_cutoff]
	today_stats = aggregate(today_rows, now)
	if not all_stats:
		return "no agents active in window"
	all_models = set(all_stats.keys()) | set(today_stats.keys())
	col_w = max(len(m) for m in all_models)
	return (
		f"=== Models (Window) ===\n{render_table(all_stats, now, show_tokens=True, col_w=col_w)}"
		f"\n\n=== Models (Today) ===\n{render_table(today_stats, now, show_tokens=True, col_w=col_w)}"
	)

def db_stamp():
	values = []
	for path in (DB_PATH, DB_PATH + "-wal"):
		try:
			values.append(os.stat(path).st_mtime_ns)
		except OSError:
			values.append(0)
	return tuple(values)

def build_report(window_hours, now):
	rows = load_stats(window_hours * 3600)
	return render(rows, now)

def draw(text):
	print(_CLEAR_SCREEN, end="")
	print(f"=== {NAME} ===")
	print(text, end="", flush=True)

def watch(window_hours):
	draw(build_report(window_hours, time.time()))
	stamp = db_stamp()
	while True:
		time.sleep(_POLL_SECONDS)
		next_stamp = db_stamp()
		if next_stamp == stamp:
			continue
		stamp = next_stamp
		draw(build_report(window_hours, time.time()))

def main():
	parser = argparse.ArgumentParser(description=f"{NAME}: per-model usage, refusals, finish reasons")
	parser.add_argument("--window-hours", type=int, default=7 * 24, help="how far back to look (default 168)")
	parser.add_argument("--watch", action="store_true", help="stay running, redraw when usage changes")
	args = parser.parse_args()
	if not os.path.exists(DB_PATH):
		print(f"{NAME}: opencode db not found: {DB_PATH}")
		return 1
	if args.watch:
		try:
			watch(args.window_hours)
		except KeyboardInterrupt:
			pass
		return 0
	print(f"=== {NAME} ===")
	print(build_report(args.window_hours, time.time()))
	return 0

if __name__ == "__main__":
	sys.exit(main())
