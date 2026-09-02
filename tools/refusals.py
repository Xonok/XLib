#!/usr/bin/env python3
"""Summarize per-model API refusals (HTTP 429) from opencode's message log.

The opencode SQLite DB records, for each assistant message that failed, an
'error' object with a statusCode. This reads those refusal events (no API
calls) and prints, per model, how many happened in the last 24h / 7 days and
how long ago count since the last one. That is a rough proxy for how close a
model is to refusing to work again.
"""
import argparse,os,sqlite3,sys,time
from collections import defaultdict

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")

def load_refusals(limit_seconds):
	conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
	cutoff = (time.time() - limit_seconds) * 1000
	rows = conn.execute(
		"""
		SELECT modelID, time_created/1000.0
		FROM message
		WHERE role = 'assistant'
			AND json_extract(data, '$.error.data.statusCode') = 429
			AND json_extract(data, '$.time.created') >= ?
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

def render(refusals, now):
	day = 60 * 60 * 24
	by_model = defaultdict(list)
	for model, created in refusals:
		by_model[model].append(created)
	if not by_model:
		return "no refusals in window"
	lines = []
	for model in sorted(by_model):
		times = by_model[model]
		day_count = sum(1 for t in times if now - t < day)
		last_age = human_age(now - max(times))
		lines.append(f"{model}: {day_count}/24h  {len(times)}/7d  last {last_age} ago")
	return "\n".join(lines)

def main():
	parser = argparse.ArgumentParser(description="Show per-model refusal counts from opencode's message log")
	parser.add_argument("--window-hours", type=int, default=7 * 24, help="how far back to look (default 168)")
	args = parser.parse_args()
	if not os.path.exists(DB_PATH):
		print(f"opencode db not found: {DB_PATH}")
		return 1
	now = time.time()
	refusals = load_refusals(args.window_hours * 3600)
	print(render(refusals, now))
	return 0

if __name__ == "__main__":
	sys.exit(main())
