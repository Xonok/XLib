#!/usr/bin/env python3
"""Keep an eye on the AI agents: per-model usage, refusals, and finish reasons.

Reads opencode's message log read-only (no API calls, so this never adds usage)
and prints per-model stats including messages, tokens, refusals, and finish reasons.

The display fits the room it is given: the caps on the two tables come from the
terminal's own height, a table that had to leave rows out says how many, and
the room a section does not need goes to the section that has more to show.
"""
import argparse,datetime,os,shutil,sqlite3,sys,time
from collections import defaultdict

NAME = "Skynet"
DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
SHOW_EXTRA = False
_CLEAR_SCREEN = "\033[2J\033[H"
_POLL_SECONDS = 1.0
_FALLBACK_SIZE = (80, 24)
# The lines the display spends before it shows a model: the Skynet header, two
# section titles, two separators and the blank between the sections.
_OVERHEAD = 6
# The lines the two sections need before they can say anything at all: the
# header, a title and a note for each of them, and the blank between.
_MINIMUM_HEIGHT = 6

def load_stats(limit_seconds):
	conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
	cutoff = (time.time() - limit_seconds) * 1000
	rows = conn.execute(
		"""
		SELECT json_extract(data, '$.model.id'),
			time_created/1000.0,
			json_extract(data, '$.tokens.input'),
			json_extract(data, '$.tokens.output'),
			COALESCE(
				json_extract(data, '$.tokens.total'),
				(COALESCE(json_extract(data, '$.tokens.input'), 0) +
				 COALESCE(json_extract(data, '$.tokens.output'), 0) +
				 COALESCE(json_extract(data, '$.tokens.reasoning'), 0) +
				 COALESCE(json_extract(data, '$.tokens.cache.read'), 0) +
				 COALESCE(json_extract(data, '$.tokens.cache.write'), 0))
			),
			json_extract(data, '$.tokens.reasoning'),
			json_extract(data, '$.tokens.cache.read'),
			json_extract(data, '$.tokens.cache.write'),
			json_extract(data, '$.error.data.statusCode'),
			json_extract(data, '$.error.name'),
			json_extract(data, '$.finish'),
			session_id
		FROM session_message
		WHERE type = 'assistant' AND json_extract(data, '$.time.created') >= ?
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

def used_models(by_model):
	"""The models worth a row: the ones that produced messages, most tokens first."""
	used = [m for m in by_model if by_model[m]["msgs"] > 0]
	return sorted(used, key=lambda m: -by_model[m]["total"])

def overflow_note(more):
	"""The line that says how much a capped table left out."""
	return f"… +{more} more"

def render_table(by_model, now, show_tokens=True, col_w=None, show_extra=False, max_models=None, title=None):
	models = used_models(by_model)
	shown = models if max_models is None else models[:max_models]
	more = len(models) - len(shown)
	label = title if title else "Model"
	if col_w is None:
		col_w = max([len(m) for m in shown] + [len(label)])
	ref_w = 12
	hdr = f"{label:<{col_w}}  {'Msgs':>5}  {'In':>7}  {'Out':>7}  {'Tot':>7}  {'Ref':>{ref_w}}"
	sep = f"{'─' * col_w}  {'─' * 5}  {'─' * 7}  {'─' * 7}  {'─' * 7}  {'─' * ref_w}"
	if show_extra:
		hdr += f"  {'Len':>4}  {'Tool':>4}  {'Stop':>4}  {'Unk':>4}"
		sep += f"  {'─' * 4}  {'─' * 4}  {'─' * 4}  {'─' * 4}"
	if not models:
		return f"{hdr}\nno agents active" if title else "no agents active"
	if not shown:
		# No room for a row at all: the note is the whole table, and the
		# separator it does not print is the line it saves.
		return f"{hdr}\n{overflow_note(more)}" if title else overflow_note(more)
	lines = [hdr, sep]
	for model in shown:
		s = by_model[model]
		ref = str(s["refusals"])
		if s["last_refusal"]:
			ref += f"({human_age(now - s['last_refusal'])})"
		if show_tokens:
			line = (f"{model:<{col_w}}"
				f"  {s['msgs']:>5}"
				f"  {human_tokens(s['input']):>7}"
				f"  {human_tokens(s['output']):>7}"
				f"  {human_tokens(s['total']):>7}"
				f"  {ref:>{ref_w}}")
		else:
			line = (f"{model:<{col_w}}"
				f"  {s['msgs']:>5}"
				f"  {ref:>{ref_w}}")
		if show_extra:
			line += f"  {s['finish_length']:>4}  {s['finish_tool_calls']:>4}  {s['finish_stop']:>4}  {s['finish_unknown']:>4}"
		lines.append(line)
	if more:
		lines.append(overflow_note(more))
	return "\n".join(lines)

def section_allowances(height, today_count, window_count):
	"""The lines each section may use for its rows and its overflow note.

	Six lines are spoken for before the first row, so what is left is split
	evenly between the two sections, and an odd line goes to Today — the view
	that comes first, and the one about now.

	The even split is the starting point, not the rule. A section with less
	to show than its share has room to spare, and the other section takes
	it: the room goes where there is something to show. Today is the smaller
	of the two by construction — the window holds everything the day holds
	and more — so in practice the spare room goes to the window.
	"""
	budget = max(height - _OVERHEAD, 0)
	today = budget // 2 + budget % 2
	window = budget // 2
	if today_count <= today and window_count > window:
		# Today shows everything it has, and Window has more to show: the
		# room Today does not need is Window's.
		today = today_count
		window = budget - today_count
	elif window_count <= window and today_count > today:
		# The other way round, for a window that holds less than the day.
		window = window_count
		today = budget - window_count
	return today, window

def row_cap(model_count, allowance):
	"""How many rows a section may show, given the lines it may use.

	A section with more to show spends one line of its allowance on the
	overflow note, so it shows one row fewer than it has room for.
	"""
	if allowance <= 0:
		return 0
	if model_count <= allowance:
		return model_count
	return allowance - 1

def terminal_size():
	"""The terminal's own size, as (columns, lines).

	The size of the process's terminal, which in a tmux pane is the pane's
	size, and a fixed fallback when stdout is not a terminal at all.
	"""
	if not sys.stdout.isatty():
		return os.terminal_size(_FALLBACK_SIZE)
	return shutil.get_terminal_size(_FALLBACK_SIZE)

def plural(count, noun):
	"""`count` and its noun, agreeing in number."""
	return f"{count} {noun}" if count == 1 else f"{count} {noun}s"

def render(rows, now, height=None):
	"""The whole display: the header, then the Today table and the Window table.

	`height` is the number of lines the display may use, and the caps on the
	tables come from it, so the render fits the room it has.
	"""
	if height is None:
		height = terminal_size().lines
	all_stats = aggregate(rows, now)
	local_midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
	today_cutoff = local_midnight.timestamp()
	today_rows = [(m, c, ti, to, tt, tr, cr, cw, s, en, f, sid)
		for m, c, ti, to, tt, tr, cr, cw, s, en, f, sid in rows if c >= today_cutoff]
	today_stats = aggregate(today_rows, now)
	today_count = len(used_models(today_stats))
	window_count = len(used_models(all_stats))
	if height < _MINIMUM_HEIGHT:
		# The two sections need six lines before they can say anything at
		# all, and a pane shorter than that gets the counts instead: a
		# truncated table must never be mistaken for the whole truth.
		if not today_count and not window_count:
			return f"{NAME}: no agents active"
		return f"{NAME}: {plural(today_count, 'model')} today, {plural(window_count, 'model')} in window"
	if not all_stats:
		return f"=== {NAME} ===\n\nno agents active in window"
	all_models = set(all_stats.keys()) | set(today_stats.keys())
	today_title = "=== Models (Today) ==="
	window_title = "=== Models (Window) ==="
	col_w = max([len(m) for m in all_models] + [len(today_title), len(window_title)])
	today_allowance, window_allowance = section_allowances(height, today_count, window_count)
	today_cap = row_cap(today_count, today_allowance)
	window_cap = row_cap(window_count, window_allowance)
	today_text = render_table(today_stats, now, show_tokens=True, col_w=col_w, show_extra=SHOW_EXTRA, max_models=today_cap, title=today_title)
	window_text = render_table(all_stats, now, show_tokens=True, col_w=col_w, show_extra=SHOW_EXTRA, max_models=window_cap, title=window_title)
	return (
		f"=== {NAME} ===\n"
		f"{today_text}"
		f"\n\n{window_text}"
	)

def db_stamp():
	values = []
	for path in (DB_PATH, DB_PATH + "-wal"):
		try:
			values.append(os.stat(path).st_mtime_ns)
		except OSError:
			values.append(0)
	return tuple(values)

def build_report(window_hours, now, height=None):
	rows = load_stats(window_hours * 3600)
	return render(rows, now, height)

def draw(text):
	print(_CLEAR_SCREEN, end="")
	print(text, end="", flush=True)

def watch(window_hours):
	draw(build_report(window_hours, time.time()))
	# The terminal's size is part of what is watched: a pane that was resized
	# has to redraw, or the old layout stays and runs off the edge.
	stamp = (db_stamp(), terminal_size())
	while True:
		time.sleep(_POLL_SECONDS)
		state = (db_stamp(), terminal_size())
		if state == stamp:
			continue
		stamp = state
		draw(build_report(window_hours, time.time()))

def main():
	parser = argparse.ArgumentParser(description=f"{NAME}: per-model usage, refusals, finish reasons")
	parser.add_argument("--window-hours", type=int, default=28 * 24, help="how far back to look (default 672)")
	parser.add_argument("--watch", action="store_true", help="stay running, redraw when usage changes")
	parser.add_argument("--extra", action="store_true", help="show extra columns (Len, Tool, Stop, Unk)")
	args = parser.parse_args()
	global SHOW_EXTRA
	SHOW_EXTRA = args.extra
	if not os.path.exists(DB_PATH):
		print(f"{NAME}: opencode db not found: {DB_PATH}")
		return 1
	if args.watch:
		try:
			watch(args.window_hours)
		except KeyboardInterrupt:
			pass
		return 0
	print(build_report(args.window_hours, time.time()))
	return 0

if __name__ == "__main__":
	sys.exit(main())
