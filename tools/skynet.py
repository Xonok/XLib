#!/usr/bin/env python3
"""Keep an eye on the AI agents: per-model usage, refusals, and finish reasons.

Reads opencode's message log read-only (no API calls, so this never adds usage)
and prints per-model stats including messages, tokens, refusals, and finish reasons.

The display fits the room it is given: the caps on the two tables come from the
terminal's own height, the columns and model names come from its width, a table
that had to leave rows out says how many, and the room a section does not need
goes to the section that has more to show.

Terminal contract: TERMINAL.md.
"""
import argparse,contextlib,ctypes,datetime,json,os,select,signal,shutil,sqlite3,struct,sys,termios,time,urllib.error,urllib.request
from collections import defaultdict
from pathlib import Path

NAME = "Skynet"
DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
STATE_PATH = os.path.expanduser("~/.local/share/skynet/quota.json")
USER_AGENT = "skynet/1.0"
HTTP_TIMEOUT = 3
QUOTA_REFRESH_SECONDS = 60
DAY_BASELINE_WINDOW = 900
MICROCENTS_PER_DOLLAR = 100_000_000
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
SHOW_EXTRA = False
_CLEAR_SCREEN = "\033[2J\033[H"
_ENTER_WATCH = "\033[?25l\033[?1049h"
_LEAVE_WATCH = "\033[?25h\033[?1049l"
_POLL_SECONDS = 1.0
_FALLBACK_SIZE = (80, 24)
_EVENT_HEADER = struct.Struct("=iIII")
_IN_MODIFY = 0x00000002
_IN_CLOSE_WRITE = 0x00000008
_IN_MOVED_TO = 0x00000080
_IN_CREATE = 0x00000100
_IN_DELETE = 0x00000200
_IN_DELETE_SELF = 0x00000400
_IN_MOVE_SELF = 0x00000800
_WATCH_MASK = _IN_MODIFY | _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE | _IN_DELETE | _IN_DELETE_SELF | _IN_MOVE_SELF
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
	HAS_INOTIFY = True
except AttributeError:
	_libc = None
	HAS_INOTIFY = False
# The lines the display spends before it shows a model: the Skynet header, two
# section titles, two separators and the blank between the sections.
_OVERHEAD = 6
# The lines the two sections need before they can say anything at all: the
# header, a title and a note for each of them, and the blank between.
_MINIMUM_HEIGHT = 6

@contextlib.contextmanager
def _fullscreen():
	"""Watch mode owns the pane: no cursor, and no scrollback of old frames."""
	_stdin_fd = None
	_old_attrs = None
	if sys.stdin.isatty():
		try:
			_stdin_fd = sys.stdin.fileno()
			_old_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs[3] &= ~(termios.ECHO | getattr(termios, "ECHOCTL", 0))
			termios.tcsetattr(_stdin_fd, termios.TCSANOW, _new_attrs)
		except (termios.error, OSError, AttributeError):
			_stdin_fd = None
			_old_attrs = None
	sys.stdout.write(_ENTER_WATCH)
	sys.stdout.flush()
	try:
		yield
	finally:
		if _old_attrs is not None and _stdin_fd is not None:
			try:
				termios.tcsetattr(_stdin_fd, termios.TCSANOW, _old_attrs)
			except (termios.error, OSError):
				pass
		sys.stdout.write(_LEAVE_WATCH)
		sys.stdout.flush()

class _Inotify:
	"""The file changes in one watched directory, read from inotify itself.

	No third-party package: the syscall is the interface, and a missing one
	is the only reason the caller falls back to polling.
	"""

	def __init__(self):
		if _libc is None:
			raise OSError("inotify is not available")
		self.fd = _libc.inotify_init()
		if self.fd == -1:
			raise OSError(ctypes.get_errno(), "inotify_init failed")
		self.dirs = {}

	def add(self, path):
		"""Watch one directory; a failure is the caller's cue to poll."""
		wd = _libc.inotify_add_watch(self.fd, os.fsencode(path), _WATCH_MASK)
		if wd == -1:
			raise OSError(ctypes.get_errno(), "inotify_add_watch failed")
		self.dirs[wd] = Path(path)

	def read(self, timeout):
		"""The (mask, path) changes in the next `timeout` seconds, if any."""
		ready, _, _ = select.select([self.fd], [], [], timeout)
		if not ready:
			return []
		raw = os.read(self.fd, 65536)
		events = []
		offset = 0
		while offset < len(raw):
			wd, mask, _, namelen = _EVENT_HEADER.unpack_from(raw, offset)
			offset += _EVENT_HEADER.size
			name = raw[offset:offset + namelen].split(b"\0", 1)[0]
			offset += (namelen + 3) & ~3
			base = self.dirs.get(wd)
			if base is not None:
				events.append((mask, base / os.fsdecode(name) if name else base))
		return events

	def close(self):
		"""Release the descriptor and every watch on it."""
		if self.fd != -1:
			os.close(self.fd)
			self.fd = -1

class _HTTPFailure(Exception):
	"""An HTTP read that did not produce JSON.

	`status` is the response code when there was one, and `None` for a
	network, timeout or decoding failure; the callers use 404 to mean "this
	account has no such product" and everything else to mean "unknown".
	"""

	def __init__(self, status=None):
		self.status = status
		super().__init__(f"HTTP {status}" if status is not None else "request failed")

def _headers(token):
	"""The headers every provider request carries; the UA is mandatory."""
	return {
		"Accept": "application/json",
		"User-Agent": USER_AGENT,
		"Authorization": f"Bearer {token}",
	}

def http_get_json(url, headers=None):
	"""One JSON read. Failures are `_HTTPFailure`, never silent.

	The explicit User-Agent is not politeness: Cloudflare rejects Python's
	default with `403 error code: 1010`.
	"""
	request_headers = dict(headers or {})
	request_headers.setdefault("Accept", "application/json")
	request_headers.setdefault("User-Agent", USER_AGENT)
	request = urllib.request.Request(url, headers=request_headers)
	try:
		with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
			body = response.read()
	except urllib.error.HTTPError as error:
		raise _HTTPFailure(error.code) from error
	except (urllib.error.URLError, TimeoutError, OSError) as error:
		raise _HTTPFailure() from error
	try:
		return json.loads(body.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise _HTTPFailure() from error

def _go_credential(rows):
	"""The active opencode credential, parsed into a source."""
	if not rows:
		return {"state": "absent"}
	try:
		value = json.loads(rows[0][0])
		return {
			"state": "ok",
			"access": value["access"],
			"expires": int(value["expires"]),
			"server": value["metadata"]["server"],
		}
	except (KeyError, TypeError, ValueError):
		return {"state": "unavailable"}

def _openrouter_credential(rows):
	"""The OpenRouter credential, parsed into a source."""
	if not rows:
		return {"state": "absent"}
	try:
		value = json.loads(rows[0][0])
		return {"state": "ok", "key": value["key"]}
	except (KeyError, TypeError, ValueError):
		return {"state": "unavailable"}

def read_credentials(db_path=None):
	"""The Go and OpenRouter credentials, read once from the local database.

	A missing row is `absent` (the provider is not configured); a row that
	cannot be parsed or a database that cannot be opened is `unavailable`.
	The connection is read-only and is never written to.
	"""
	sources = {"go": {"state": "unavailable"}, "openrouter": {"state": "unavailable"}}
	try:
		conn = sqlite3.connect(f"file:{db_path or DB_PATH}?mode=ro", uri=True)
		try:
			go_rows = conn.execute(
				"SELECT value FROM credential WHERE integration_id = 'opencode' AND active = 1 ORDER BY time_updated DESC"
			).fetchall()
			openrouter_rows = conn.execute(
				"SELECT value FROM credential WHERE integration_id = 'openrouter' ORDER BY COALESCE(active, 0) DESC, time_updated DESC"
			).fetchall()
		finally:
			conn.close()
	except sqlite3.Error:
		return sources
	sources["go"] = _go_credential(go_rows)
	sources["openrouter"] = _openrouter_credential(openrouter_rows)
	return sources

def _parse_time(text):
	"""An ISO timestamp with an explicit zone; `Z` is `+00:00`."""
	if not isinstance(text, str):
		raise ValueError("time is not a string")
	value = text[:-1] + "+00:00" if text.endswith("Z") else text
	parsed = datetime.datetime.fromisoformat(value)
	if parsed.tzinfo is None:
		raise ValueError("time has no timezone")
	return parsed

def go_quota(credential, now, fetch):
	"""The Go month meter, or the reason it cannot be shown.

	`404` and a null `access` mean the account has no Go product (`absent`);
	every other failure is `unavailable`, never an exception into the renderer.
	"""
	if credential["state"] != "ok":
		return {"state": credential["state"]}
	if credential["expires"] <= now.timestamp() * 1000:
		return {"state": "unavailable"}
	url = credential["server"].rstrip("/") + "/api/go/status"
	try:
		data = fetch(url, _headers(credential["access"]))
	except _HTTPFailure as error:
		return {"state": "absent"} if error.status == 404 else {"state": "unavailable"}
	except (LookupError, TypeError, ValueError, OSError):
		return {"state": "unavailable"}
	try:
		product = data["product"]
		access = data["access"]
	except (KeyError, TypeError):
		return {"state": "unavailable"}
	if access is None:
		return {"state": "absent"}
	try:
		start = _parse_time(access["startsAt"])
		end = _parse_time(access["endsAt"])
		meter = access["meters"]["month"]
		limit = int(meter["limitMicroCents"])
		used = int(meter["usedMicroCents"])
	except (KeyError, TypeError, ValueError):
		return {"state": "unavailable"}
	if product not in ("go", "go-plus"):
		return {"state": "unavailable"}
	return {
		"state": "ok",
		"product": product,
		"start": start,
		"end": end,
		"period_start": access["startsAt"],
		"limit": limit,
		"used": used,
	}

def openrouter_quota(credential, fetch):
	"""The OpenRouter free-model daily counter, or the reason it is missing."""
	if credential["state"] != "ok":
		return {"state": credential["state"]}
	try:
		data = fetch(OPENROUTER_KEY_URL, _headers(credential["key"]))
	except (_HTTPFailure, LookupError, TypeError, ValueError, OSError):
		return {"state": "unavailable"}
	try:
		payload = data["data"] if isinstance(data, dict) and "data" in data else data
		daily = payload["free_model_daily_requests"]
		return {"state": "ok", "used": int(daily["used"]), "limit": int(daily["limit"])}
	except (KeyError, TypeError, ValueError):
		return {"state": "unavailable"}

def compute_pace(go, day_start_used, now):
	"""The used percentage and the two rates, as percentages of sustainable.

	`overall` divides the used meter by the elapsed days since the period
	start; `today` divides the day's increase by the elapsed day. Both are
	`None` when their denominator is missing or non-positive, and a meter
	that fell below the baseline cannot give a rate.
	"""
	pace = {"used_percent": None, "overall": None, "today": None}
	if go["state"] != "ok":
		return pace
	limit = go["limit"]
	used = go["used"]
	if limit > 0:
		pace["used_percent"] = used / limit * 100
	period_days = (go["end"] - go["start"]).total_seconds() / 86400
	if period_days <= 0 or limit <= 0:
		return pace
	sustainable = limit / period_days
	elapsed = (now - go["start"]).total_seconds() / 86400
	if elapsed > 0:
		pace["overall"] = (used / elapsed) / sustainable * 100
	local = now.astimezone()
	day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
	day_elapsed = (local - day_start).total_seconds() / 86400
	if day_start_used is not None and used >= day_start_used and day_elapsed > 0:
		pace["today"] = ((used - day_start_used) / day_elapsed) / sustainable * 100
	return pace

def _number(value):
	"""A stored timestamp or meter reading, or `None` when it is not a number."""
	if isinstance(value, bool) or not isinstance(value, (int, float)):
		return None
	return value

def _load_day_state(state_path):
	"""The stored Go day baseline, or an empty one when missing or corrupt."""
	try:
		with open(state_path, encoding="utf-8") as file:
			state = json.load(file)
	except (OSError, TypeError, ValueError):
		return {}
	if not isinstance(state, dict):
		return {}
	go = state.get("go")
	return go if isinstance(go, dict) else {}

def _write_day_state(state_path, go_state):
	"""Replace the state atomically, so a crash never leaves half a file."""
	path = Path(state_path)
	path.parent.mkdir(parents=True, exist_ok=True)
	temporary = path.with_name(path.name + ".tmp")
	with open(temporary, "w", encoding="utf-8") as file:
		json.dump({"version": 1, "go": go_state}, file, sort_keys=True)
		file.write("\n")
	os.replace(temporary, path)

def update_day_state(state_path, go, now):
	"""The midnight meter reading to measure today against, and persist it.

	The provider has no daily history, so today's baseline is the reading
	taken near local midnight: a rollover reuses the last reading only when
	`last_seen` is within `DAY_BASELINE_WINDOW` seconds of midnight. A new
	paid period, a meter that fell, or a write failure all leave the baseline
	unknown (`today ?`) rather than guessing.
	"""
	if go["state"] != "ok":
		return None
	stored = _load_day_state(state_path)
	local = now.astimezone()
	today = local.date().isoformat()
	local_midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
	last_seen = _number(stored.get("last_seen"))
	last_used = _number(stored.get("last_used"))
	if stored.get("day") != today:
		baseline = None
		if last_seen is not None and abs(last_seen - local_midnight.timestamp()) <= DAY_BASELINE_WINDOW:
			baseline = last_used
	else:
		baseline = _number(stored.get("day_start_used"))
	if stored.get("period_start") != go["period_start"]:
		baseline = None
	if last_used is not None and go["used"] < last_used:
		baseline = None
	state = {
		"day": today,
		"day_start_used": baseline,
		"last_used": go["used"],
		"last_seen": int(now.timestamp()),
		"period_start": go["period_start"],
	}
	try:
		_write_day_state(state_path, state)
	except (OSError, TypeError, ValueError):
		return None
	return baseline

def sample_quota(now=None, state_path=None, fetch=None, db_path=None):
	"""Both quotas at one instant, with the day baseline updated.

	A failed source becomes `unavailable`; it never raises, so the tables
	always render.
	"""
	if now is None:
		now = datetime.datetime.now().astimezone()
	read = fetch or http_get_json
	credentials = read_credentials(db_path)
	go = go_quota(credentials["go"], now, read)
	openrouter = openrouter_quota(credentials["openrouter"], read)
	baseline = update_day_state(state_path or STATE_PATH, go, now) if go["state"] == "ok" else None
	return {"go": go, "openrouter": openrouter, "pace": compute_pace(go, baseline, now)}

def _dollars(microcents, exact=False):
	"""Microcents as dollars; an exact integral amount has no decimals."""
	if exact and microcents % MICROCENTS_PER_DOLLAR == 0:
		return f"${microcents // MICROCENTS_PER_DOLLAR}"
	return f"${microcents / MICROCENTS_PER_DOLLAR:.2f}"

def _percent(value):
	return f"{round(value)}%" if value is not None else "?"

def _go_variants(quota):
	"""The Go field, longest first: limit, then used, then the percentage alone."""
	go = quota.get("go") or {}
	if go.get("state") != "ok":
		return []
	pace = quota.get("pace") or {}
	label = "G+" if go.get("product") == "go-plus" else "G"
	used = _dollars(go["used"])
	limit = _dollars(go["limit"], exact=True)[1:]
	percent = _percent(pace.get("used_percent"))
	return [
		f"{label} {used}/{limit} {percent}",
		f"{label} {used} {percent}",
		f"{label} {percent}",
	]

def _quota_fields(quota, abbreviated):
	"""The first line's fields, in display order, for one of the two forms."""
	go = quota.get("go") or {"state": "absent"}
	pace = quota.get("pace") or {}
	fields = []
	if go.get("state") == "ok":
		label = "Go+" if go.get("product") == "go-plus" else "Go"
		if abbreviated:
			label = "G+" if label == "Go+" else "G"
		used = _dollars(go["used"])
		limit = _dollars(go["limit"], exact=True)
		if abbreviated:
			limit = limit[1:]
		fields.append(f"{label} {used}/{limit} {_percent(pace.get('used_percent'))}")
		if pace.get("overall") is not None:
			fields.append(f"p {round(pace['overall'])}" if abbreviated else f"pace {round(pace['overall'])}%/d")
		if pace.get("today") is not None:
			fields.append(f"t {round(pace['today'])}" if abbreviated else f"today {round(pace['today'])}%/d")
		else:
			fields.append("t ?" if abbreviated else "today ?")
	elif go.get("state") == "unavailable":
		fields.append("G ?" if abbreviated else "Go ?")
	openrouter = quota.get("openrouter") or {"state": "absent"}
	if openrouter.get("state") == "ok":
		fields.append(f"OR {openrouter['used']}/{openrouter['limit']}")
	elif openrouter.get("state") == "unavailable":
		fields.append("OR ?")
	return fields

def _quota_text(title, fields):
	if not fields:
		return title
	return title + " " + " · ".join(fields)

def quota_line(quota, width):
	"""The first line: full form, abbreviated form, then fields dropped.

	Never returns more than `width` characters, and never a newline. The
	abbreviated form keeps every field; only when it still does not fit are
	fields dropped, from the right (`OR`, `today`, `pace`), then the Go field
	is shortened to its percentage alone, then the title.
	"""
	title = f"=== {NAME} ==="
	if quota is None:
		return title if len(title) <= width else title[:width]
	line = _quota_text(title, _quota_fields(quota, False))
	if len(line) <= width:
		return line
	fields = _quota_fields(quota, True)
	line = _quota_text(title, fields)
	if len(line) <= width:
		return line
	while len(fields) > 1:
		fields = fields[:-1]
		line = _quota_text(title, fields)
		if len(line) <= width:
			return line
	for variant in _go_variants(quota)[1:]:
		line = _quota_text(title, [variant])
		if len(line) <= width:
			return line
	return title if len(title) <= width else title[:width]

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

_COLUMNS = (("Msgs",5),("In",7),("Out",7),("Tot",7),("Ref",12))
_EXTRA_COLUMNS = (("Len",4),("Tool",4),("Stop",4),("Unk",4))
_MIN_MODEL_WIDTH = 8

def fit_columns(width, show_extra=False, show_tokens=True):
	"""The columns and model width that fit `width`, dropping the least first.

	Tot repeats what In and Out already say, so it goes before either of
	them; then the token columns, then Ref, then Msgs. The model column keeps
	at least `_MIN_MODEL_WIDTH` until there is nothing left to drop.
	"""
	columns = list(_COLUMNS if show_tokens else (("Msgs",5),("Ref",12)))
	if show_extra:
		columns += list(_EXTRA_COLUMNS)
	def fixed():
		return sum(w for _,w in columns) + 2 * len(columns)
	def drop(names):
		nonlocal columns
		columns = [column for column in columns if column[0] not in names]
	while columns and width - fixed() < _MIN_MODEL_WIDTH:
		extras = {name for name,_ in _EXTRA_COLUMNS}
		if any(name in extras for name,_ in columns):
			drop(extras)
			continue
		for name in ("Tot","In","Out","Ref","Msgs"):
			if any(column == name for column,_ in columns):
				drop({name})
				break
		else:
			break
	return columns, max(1, width - fixed())

def fit_cell(text, width):
	"""One cell, cut to the room it has."""
	if len(text) <= width:
		return text
	if width <= 1:
		return text[:width]
	return text[:width - 1] + "…"

def cell(stats, name, width, now):
	"""One value from a model's stats, aligned to its column."""
	if name == "Msgs":
		return f"{stats['msgs']:>{width}}"
	if name == "In":
		return f"{human_tokens(stats['input']):>{width}}"
	if name == "Out":
		return f"{human_tokens(stats['output']):>{width}}"
	if name == "Tot":
		return f"{human_tokens(stats['total']):>{width}}"
	if name == "Ref":
		ref = str(stats["refusals"])
		if stats["last_refusal"]:
			ref += f"({human_age(now - stats['last_refusal'])})"
		return f"{fit_cell(ref,width):>{width}}"
	if name == "Len":
		return f"{stats['finish_length']:>{width}}"
	if name == "Tool":
		return f"{stats['finish_tool_calls']:>{width}}"
	if name == "Stop":
		return f"{stats['finish_stop']:>{width}}"
	return f"{stats['finish_unknown']:>{width}}"

def render_table(by_model, now, show_tokens=True, col_w=None, show_extra=False, max_models=None, title=None, columns=None):
	models = used_models(by_model)
	shown = models if max_models is None else models[:max_models]
	more = len(models) - len(shown)
	label = title if title else "Model"
	if columns is None:
		columns = list(_COLUMNS if show_tokens else (("Msgs",5),("Ref",12)))
		if show_extra:
			columns += list(_EXTRA_COLUMNS)
	if col_w is None:
		col_w = max([len(m) for m in shown] + [len(label)])
	hdr = f"{fit_cell(label,col_w):<{col_w}}"
	sep = "─" * col_w
	for name,width in columns:
		hdr += f"  {name:>{width}}"
		sep += "  " + "─" * width
	if not models:
		return f"{hdr}\nno agents active" if title else "no agents active"
	if not shown:
		# No room for a row at all: the note is the whole table, and the
		# separator it does not print is the line it saves.
		return f"{hdr}\n{overflow_note(more)}" if title else overflow_note(more)
	lines = [hdr, sep]
	for model in shown:
		line = f"{fit_cell(model,col_w):<{col_w}}"
		for name,width in columns:
			line += "  " + cell(by_model[model], name, width, now)
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

def render(rows, now, height=None, width=None, quota=None):
	"""The whole display: the header, then the Today table and the Window table.

	`height` is the number of lines the display may use, and `width` the
	columns it may use; the caps on the rows come from the first, the columns
	and the model names from the second, so the render fits the pane it has.
	`quota` is a `sample_quota` result; without one the header is unchanged.
	"""
	if height is None or width is None:
		size = terminal_size()
		if height is None:
			height = size.lines
		if width is None:
			width = size.columns
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
		return f"{quota_line(quota, width)}\n\nno agents active in window"
	columns, col_w = fit_columns(width, SHOW_EXTRA)
	today_title = "=== Models (Today) ==="
	window_title = "=== Models (Window) ==="
	# A title that no longer fits gives way to the short name; the column
	# labels ride on the same line and are worth more than the brackets.
	if len(today_title) > col_w:
		today_title = "Today"
	if len(window_title) > col_w:
		window_title = "Window"
	today_allowance, window_allowance = section_allowances(height, today_count, window_count)
	today_cap = row_cap(today_count, today_allowance)
	window_cap = row_cap(window_count, window_allowance)
	today_text = render_table(today_stats, now, show_tokens=True, col_w=col_w, show_extra=SHOW_EXTRA, max_models=today_cap, title=today_title, columns=columns)
	window_text = render_table(all_stats, now, show_tokens=True, col_w=col_w, show_extra=SHOW_EXTRA, max_models=window_cap, title=window_title, columns=columns)
	return (
		f"{quota_line(quota, width)}\n"
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

def build_report(window_hours, now, height=None, width=None, quota=None):
	rows = load_stats(window_hours * 3600)
	return render(rows, now, height, width, quota)

def draw(text):
	print(_CLEAR_SCREEN, end="")
	print(text, end="", flush=True)

def _db_watcher():
	"""An inotify watch on the database's directory, or None to poll.

	The writes that matter are SQLite's own: the database file and its WAL.
	The directory is what is watched, because the WAL appears beside the
	database and is not there when the tool starts.
	"""
	if not HAS_INOTIFY:
		return None
	watcher = None
	try:
		watcher = _Inotify()
		watcher.add(Path(DB_PATH).parent)
	except OSError:
		if watcher is not None:
			watcher.close()
		return None
	return watcher

def watch(window_hours):
	with _fullscreen():
		quota = sample_quota()
		quota_due = time.monotonic() + QUOTA_REFRESH_SECONDS
		draw(build_report(window_hours, time.time(), quota=quota))
		# The terminal's size is part of what is watched: a pane that was resized
		# has to redraw, or the old layout stays and runs off the edge. The pace
		# also changes with time, so the quota timer wakes the loop even when the
		# database does not.
		size = terminal_size()
		watcher = _db_watcher()
		stamp = db_stamp()
		try:
			while True:
				changed = False
				if watcher is not None:
					changed = any(path.name.startswith("opencode.db") for _, path in watcher.read(_POLL_SECONDS))
				else:
					time.sleep(_POLL_SECONDS)
					current = db_stamp()
					changed = current != stamp
					stamp = current
				refresh_quota = time.monotonic() >= quota_due
				current_size = terminal_size()
				if not changed and current_size == size and not refresh_quota:
					continue
				if refresh_quota:
					quota = sample_quota()
					quota_due = time.monotonic() + QUOTA_REFRESH_SECONDS
				size = current_size
				draw(build_report(window_hours, time.time(), quota=quota))
		finally:
			if watcher is not None:
				watcher.close()

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
		signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
		try:
			watch(args.window_hours)
		except KeyboardInterrupt:
			pass
		return 0
	quota = sample_quota()
	print(build_report(args.window_hours, time.time(), quota=quota))
	return 0

if __name__ == "__main__":
	sys.exit(main())
