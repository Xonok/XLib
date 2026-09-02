#!/usr/bin/env python3
"""Keep an eye on the AI agents: per-model usage and refusal counts.

Reads opencode's message log read-only (no API calls, so this never adds usage)
and prints, per model, how many assistant messages and tokens it produced in the
last window, plus how many times it was refused (HTTP 429) and how long ago the
last refusal was. Message and token counts show how work is spread between
models; refusals are a rough proxy for how close a model is to refusing again.
"""
import argparse,os,sqlite3,sys,time
from collections import defaultdict

NAME = "Skynet"
DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")

def load_stats(limit_seconds):
	conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
	cutoff = (time.time() - limit_seconds) * 1000
	rows = conn.execute(
		"""
		SELECT modelID,
			time_created/1000.0,
			json_extract(data, '$.tokens.input'),
			json_extract(data, '$.tokens.output'),
			json_extract(data, '$.tokens.total'),
			json_extract(data, '$.error.data.statusCode')
		FROM message
		WHERE role = 'assistant' AND json_extract(data, '$.time.created') >= ?
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

def render(rows, now):
	by_model = defaultdict(lambda: {"msgs": 0, "input": 0, "output": 0, "total": 0, "refusals": 0, "last_refusal": 0})
	for model, created, token_in, token_out, token_total, status in rows:
		stats = by_model[model]
		stats["msgs"] += 1
		if token_in is not None:
			stats["input"] += int(token_in)
		if token_out is not None:
			stats["output"] += int(token_out)
		if token_total is not None:
			stats["total"] += int(token_total)
		if status == 429:
			stats["refusals"] += 1
			stats["last_refusal"] = max(stats["last_refusal"], created)
	if not by_model:
		return "no agents active in window"
	lines = []
	for model in sorted(by_model, key=lambda m: -by_model[m]["total"]):
		s = by_model[model]
		ref = f", {s['refusals']} refusal(s)" if s["refusals"] else ""
		last = f", last {human_age(now - s['last_refusal'])} ago" if s["last_refusal"] else ""
		lines.append(
			f"{model}: {s['msgs']} msgs"
			f" {human_tokens(s['input'])} in / {human_tokens(s['output'])} out / {human_tokens(s['total'])} total"
			f"{ref}{last}"
		)
	return "\n".join(lines)

def main():
	parser = argparse.ArgumentParser(description=f"{NAME}: per-model usage and refusal counts")
	parser.add_argument("--window-hours", type=int, default=7 * 24, help="how far back to look (default 168)")
	args = parser.parse_args()
	if not os.path.exists(DB_PATH):
		print(f"{NAME}: opencode db not found: {DB_PATH}")
		return 1
	now = time.time()
	rows = load_stats(args.window_hours * 3600)
	print(f"=== {NAME} ===")
	print(render(rows, now))
	return 0

if __name__ == "__main__":
	sys.exit(main())
