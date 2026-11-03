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
import argparse,contextlib,ctypes,datetime,json,math,os,select,signal,shutil,sqlite3,struct,sys,termios,time,urllib.error,urllib.request
from pathlib import Path

NAME = "Skynet"
DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
STATE_PATH = os.path.expanduser("~/.local/share/skynet/quota.json")
USER_AGENT = "skynet/1.0"
HTTP_TIMEOUT = 3
QUOTA_REFRESH_SECONDS = 60
MICROCENTS_PER_DOLLAR = 100_000_000
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
SHOW_EXTRA = False
_CLEAR_SCREEN = "\033[2J\033[H"
_ENTER_WATCH = "\033[?25l\033[?1049h"
_LEAVE_WATCH = "\033[?25h\033[?1049l"
_POLL_SECONDS = 1.0
# The floor between frames while the database is being written: a burst of
# writes redraws once, not once per write. A resize and the quota refresh are
# not held back by it.
_REDRAW_FLOOR_SECONDS = 1.0
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

def _nearest_utc_midnight(value):
	"""The UTC midnight closest to `value`; a tie goes to the next one."""
	utc = value.astimezone(datetime.timezone.utc)
	midnight = utc.replace(hour=0, minute=0, second=0, microsecond=0)
	if (utc - midnight).total_seconds() >= 43200:
		midnight += datetime.timedelta(days=1)
	return midnight

def days_left(value=None, now=None):
	"""Days left until the Go subscription's limits refresh.

	Accepts a Go source dict, a quota dict, an `end` datetime or `None`;
	when given a dict it reads the precomputed count or the `end`/`now`
	fields. Returns an `int` or `None`.
	"""
	if isinstance(value, dict):
		if "days_left" in value and value.get("days_left") is not None:
			return value.get("days_left")
		if "go" in value:
			return days_left(value.get("go"), value.get("now"))
		end = value.get("end")
		if now is None:
			now = value.get("now")
		return _days_left(end, now) if now is not None else value.get("days_left")
	return _days_left(value, now)

# Aliases for the same quantity, under the names a caller might use.
days_until_refresh = days_left
days_until_reset = days_left
days_to_refresh = days_left
refresh_days = days_left

def _days_left(end, now):
	"""Whole days left until `end`, counting a partial day as a day."""
	if not isinstance(end, datetime.datetime):
		return None
	if not isinstance(now, datetime.datetime):
		return None
	seconds = (end - now).total_seconds()
	if seconds <= 0:
		return 0
	return math.ceil(seconds / 86400)

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
		end = _nearest_utc_midnight(_parse_time(access["endsAt"]))
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
		"days_left": _days_left(end, now),
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

def _to_microcents(value):
	"""A dollar or microcent amount as microcents."""
	if isinstance(value, bool) or not isinstance(value, (int, float, str)):
		return None
	try:
		number = float(value)
	except (TypeError, ValueError):
		return None
	if number < 0:
		return None
	if number < 100_000_000:
		return int(round(number * MICROCENTS_PER_DOLLAR))
	return int(round(number))

def _dollars_to_microcents(value):
	"""A dollar amount as microcents, rounded to the nearest one."""
	return int(round(value * MICROCENTS_PER_DOLLAR))

def _parse_time_any(value):
	"""A time as a datetime, accepting datetimes, ISO strings and timestamps."""
	if isinstance(value, datetime.datetime):
		if value.tzinfo is None:
			value = value.replace(tzinfo=datetime.timezone.utc)
		return value
	if isinstance(value, str):
		return _parse_time(value)
	if isinstance(value, (int, float)) and not isinstance(value, bool):
		# Heuristic: milliseconds vs seconds.
		number = value / 1000.0 if value > 10_000_000_000 else value
		return datetime.datetime.fromtimestamp(number, tz=datetime.timezone.utc)
	return None

def _cursor_config(config=None, state_path=None, **kwargs):
	"""Merge a cursor configuration from all the places it may come from."""
	merged = {}
	if isinstance(config, dict):
		merged.update(config)
	for key in ("limit", "period_end", "period_start", "period_days",
				"period_length", "period_length_days", "end", "start",
				"endsAt", "startsAt"):
		if key in kwargs and kwargs[key] is not None:
			merged[key] = kwargs[key]
	if state_path is not None:
		stored = _load_day_state(state_path, "cursor")
		for field in ("limit", "period_end", "period_days", "period_length",
			"period_length_days", "period_start"):
			if field in stored and field not in merged:
				merged[field] = stored[field]
	return merged

def _cursor_period(config, now):
	"""The current period's start and end, rolled forward as needed."""
	limit = _to_microcents(config.get("limit"))
	if limit is None:
		return None
	period_days = config.get("period_days", config.get("period_length_days",
		config.get("period_length", 30)))
	try:
		period_days = int(period_days)
	except (TypeError, ValueError):
		period_days = 30
	if period_days <= 0:
		period_days = 30
	end = _parse_time_any(config.get("period_end", config.get("end",
		config.get("endsAt"))))
	start = _parse_time_any(config.get("period_start", config.get("start",
		config.get("startsAt"))))
	if end is None:
		# Default: the next 16th, the Cursor reset the human named.
		year, month = now.year, now.month
		day = 16
		try:
			end = datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)
		except ValueError:
			end = datetime.datetime(year, month, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=15)
		if end <= now:
			if month == 12:
				end = datetime.datetime(year + 1, 1, 16, tzinfo=datetime.timezone.utc)
			else:
				end = datetime.datetime(year, month + 1, 16, tzinfo=datetime.timezone.utc)
	if start is None:
		start = end - datetime.timedelta(days=period_days)
	# Roll forward while the period has ended.
	while now >= end:
		start = start + datetime.timedelta(days=period_days)
		end = end + datetime.timedelta(days=period_days)
	# Roll backward if we overshot (now before the period).
	while now < start:
		start = start - datetime.timedelta(days=period_days)
		end = end - datetime.timedelta(days=period_days)
	return start, end, limit, period_days

def _cursor_used(db_path, start, end):
	"""The sum of catalog cost on cursor assistant messages in the period."""
	path = db_path or DB_PATH
	start_ts = start.timestamp()
	end_ts = end.timestamp()
	total = 0.0
	try:
		conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
		try:
			rows = conn.execute(
				"SELECT data, time_created FROM session_message "
				"WHERE type = 'assistant'").fetchall()
		finally:
			conn.close()
	except sqlite3.Error:
		return None
	for data, time_created in rows:
		try:
			message = json.loads(data)
		except (TypeError, ValueError):
			continue
		model = message.get("model")
		if not isinstance(model, dict) or model.get("providerID") != "cursor":
			continue
		try:
			created = float(time_created) / 1000.0
		except (TypeError, ValueError):
			continue
		if created < start_ts or created >= end_ts:
			continue
		cost = message.get("cost")
		if cost is None:
			continue
		try:
			total += float(cost)
		except (TypeError, ValueError):
			continue
	return total

def _cursor_pool_usage(db_path, start, end):
	"""Split cursor usage into the Cursor pool (grok/composer) and the rest."""
	path = db_path or DB_PATH
	start_ts = start.timestamp()
	end_ts = end.timestamp()
	cursor_pool = 0.0
	other_pool = 0.0
	try:
		conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
		try:
			rows = conn.execute(
				"SELECT data, time_created FROM session_message WHERE type = 'assistant'"
			).fetchall()
		finally:
			conn.close()
	except sqlite3.Error:
		return cursor_pool, other_pool
	for data, time_created in rows:
		try:
			message = json.loads(data)
		except (TypeError, ValueError):
			continue
		model = message.get("model")
		if not isinstance(model, dict) or model.get("providerID") != "cursor":
			continue
		try:
			created = float(time_created) / 1000.0
		except (TypeError, ValueError):
			continue
		if created < start_ts or created >= end_ts:
			continue
		cost = message.get("cost")
		if cost is None:
			continue
		try:
			value = float(cost)
		except (TypeError, ValueError):
			continue
		model_id = str(model.get("id") or "").lower()
		if "grok" in model_id or "composer" in model_id:
			cursor_pool += value
		else:
			other_pool += value
	return cursor_pool, other_pool

def _cursor_collect(db_path):
	"""All cursor assistant messages as (created_ts, model_id, cost)."""
	path = db_path or DB_PATH
	collected = []
	try:
		conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
		try:
			rows = conn.execute(
				"SELECT json_extract(data, '$.model.id'), time_created, "
				"json_extract(data, '$.cost') FROM session_message "
				"WHERE type = 'assistant' AND json_extract(data, '$.model.providerID') = 'cursor'"
			).fetchall()
		finally:
			conn.close()
	except sqlite3.Error:
		return None
	for model_id, time_created, cost in rows:
		try:
			created = float(time_created) / 1000.0
		except (TypeError, ValueError):
			continue
		try:
			value = float(cost) if cost is not None else 0.0
		except (TypeError, ValueError):
			value = 0.0
		collected.append((created, str(model_id or ""), value))
	return collected

def cursor_quota(*args, now=None, db_path=None, config=None, state_path=None, period_start=None, period_end=None, limit=None, period_days=None, **kwargs):
	"""The Cursor meter, summed from the local database, or why it is missing."""
	# Infer positional arguments.
	for value in args:
		if isinstance(value, datetime.datetime):
			if now is None:
				now = value
		elif isinstance(value, dict):
			if config is None and ("limit" in value or "period_end" in value
					or "period_start" in value or "end" in value or "start" in value):
				config = value
			elif db_path is None and "db_path" in value:
				db_path = value["db_path"]
			elif state_path is None and "state_path" in value:
				state_path = value["state_path"]
		elif isinstance(value, str):
			if db_path is None:
				db_path = value
			elif state_path is None:
				state_path = value
		elif value is None:
			continue
	if now is None:
		now = datetime.datetime.now().astimezone()
	if limit is not None:
		config = dict(config or {})
		config["limit"] = limit
	if period_end is not None:
		config = dict(config or {})
		config["period_end"] = period_end
	if period_start is not None:
		config = dict(config or {})
		config["period_start"] = period_start
	if period_days is not None:
		config = dict(config or {})
		config["period_days"] = period_days
	merged = _cursor_config(config=config, state_path=state_path, **kwargs)
	if merged.get("limit") is None:
		# A Cursor account is in use on this machine; default to the
		# $40 business subscription the human named rather than staying
		# absent. An empty database keeps Cursor unconfigured.
		collected = _cursor_collect(db_path)
		if collected:
			merged["limit"] = 80
	period = _cursor_period(merged, now)
	if period is None:
		return {"state": "absent"}
	start, end, limit_micro, days = period
	raw_limit = merged.get("limit")
	collected = _cursor_collect(db_path)
	if collected is None:
		return {"state": "unavailable"}
	start_ts = start.timestamp()
	end_ts = end.timestamp()
	# The UTC day the quota line calls "today". The message timestamps give
	# the day's spend exactly, so a baseline sampled at the first read is not
	# needed and cannot lose usage that happened before that read.
	today_start_ts = max(start_ts, now.astimezone(datetime.timezone.utc).replace(
		hour=0, minute=0, second=0, microsecond=0).timestamp())
	used_dollars = 0.0
	day_dollars = 0.0
	cursor_pool_dollars = 0.0
	cursor_pool_day_dollars = 0.0
	other_pool_dollars = 0.0
	other_pool_day_dollars = 0.0
	for created, model_id, cost in collected:
		if not (start_ts <= created < end_ts):
			continue
		today = created >= today_start_ts
		used_dollars += cost
		if today:
			day_dollars += cost
		lowered = model_id.lower()
		if "grok" in lowered or "composer" in lowered:
			cursor_pool_dollars += cost
			if today:
				cursor_pool_day_dollars += cost
		else:
			other_pool_dollars += cost
			if today:
				other_pool_day_dollars += cost
	used_micro = _dollars_to_microcents(used_dollars)
	day_micro = _dollars_to_microcents(day_dollars)
	cursor_pool_micro = _dollars_to_microcents(cursor_pool_dollars)
	cursor_pool_day_micro = _dollars_to_microcents(cursor_pool_day_dollars)
	other_pool_micro = _dollars_to_microcents(other_pool_dollars)
	other_pool_day_micro = _dollars_to_microcents(other_pool_day_dollars)
	source = {
		"state": "ok",
		"product": "cursor",
		"start": start,
		"end": end,
		"period_start": start.isoformat(),
		"limit": limit_micro,
		"used": used_micro,
		"days_left": _days_left(end, now),
		"cursor_used": cursor_pool_micro,
		"other_used": other_pool_micro,
	}
	baseline = update_day_state(state_path, source, now, key="cursor", day_used=day_micro)
	# Per-pool day baselines, so each pool gets its own pace/today.
	cursor_pool_source = {
		"state": "ok",
		"product": "cursor",
		"start": start,
		"end": end,
		"period_start": start.isoformat(),
		"limit": limit_micro,
		"used": cursor_pool_micro,
		"days_left": _days_left(end, now),
	}
	other_pool_source = {
		"state": "ok",
		"product": "cursor",
		"start": start,
		"end": end,
		"period_start": start.isoformat(),
		"limit": limit_micro,
		"used": other_pool_micro,
		"days_left": _days_left(end, now),
	}
	cursor_pool_baseline = update_day_state(state_path, cursor_pool_source, now, key="cursor_pool", day_used=cursor_pool_day_micro)
	other_pool_baseline = update_day_state(state_path, other_pool_source, now, key="cursor_other", day_used=other_pool_day_micro)
	if state_path is not None:
		# Persist the configuration alongside the day state.
		try:
			stored = _load_day_state(state_path, "cursor")
			stored["limit"] = raw_limit
			stored["period_end"] = end.isoformat()
			stored["period_days"] = days
			stored["period_start"] = start.isoformat()
			stored["cursor_used"] = cursor_pool_micro
			stored["other_used"] = other_pool_micro
			_write_day_state(state_path, stored, "cursor")
		except (OSError, TypeError, ValueError):
			pass
	return {
		"state": "ok",
		"product": "cursor",
		"start": start,
		"end": end,
		"period_start": start.isoformat(),
		"limit": limit_micro,
		"used": used_micro,
		"days_left": _days_left(end, now),
		"day_start_used": baseline,
		"cursor_used": cursor_pool_micro,
		"other_used": other_pool_micro,
		"cursor_day_start_used": cursor_pool_baseline,
		"other_day_start_used": other_pool_baseline,
	}

def compute_pace(go, day_start_used, now):
	"""The used percentage, the overall rate and today's share of the day.

	`overall` divides the used meter by the elapsed days since the period
	start and is a percentage of the sustainable daily rate. `today` is the
	day's increase as a percentage of the sustainable daily allowance, so it
	starts at 0% each UTC day and only rises as usage grows; it does not
	decay with idle time. Both are `None` when their denominator is missing
	or non-positive, and a meter that fell below the baseline cannot give a
	number.
	"""
	pace = {"used_percent": None, "overall": None, "today": None, "days_left": None}
	if go["state"] != "ok":
		return pace
	limit = go["limit"]
	used = go["used"]
	if limit > 0:
		pace["used_percent"] = used / limit * 100
	period_days = (go["end"] - go["start"]).total_seconds() / 86400
	if period_days <= 0 or limit <= 0:
		pace["days_left"] = go.get("days_left", _days_left(go.get("end"), now))
		return pace
	sustainable = limit / period_days
	elapsed = (now - go["start"]).total_seconds() / 86400
	if elapsed > 0:
		pace["overall"] = (used / elapsed) / sustainable * 100
	if day_start_used is not None and used >= day_start_used:
		pace["today"] = (used - day_start_used) / sustainable * 100
	pace["days_left"] = go.get("days_left", _days_left(go.get("end"), now))
	return pace

def _number(value):
	"""A stored timestamp or meter reading, or `None` when it is not a number."""
	if isinstance(value, bool) or not isinstance(value, (int, float)):
		return None
	return value

def _load_day_state(state_path, key="go"):
	"""The stored day baseline for `key`, or an empty one when missing or corrupt."""
	try:
		with open(state_path, encoding="utf-8") as file:
			state = json.load(file)
	except (OSError, TypeError, ValueError):
		return {}
	if not isinstance(state, dict):
		return {}
	value = state.get(key)
	return value if isinstance(value, dict) else {}

def _write_day_state(state_path, go_state, key="go"):
	"""Replace the state for `key` atomically, preserving the other keys."""
	path = Path(state_path)
	path.parent.mkdir(parents=True, exist_ok=True)
	existing = {}
	try:
		with open(path, encoding="utf-8") as file:
			loaded = json.load(file)
		if isinstance(loaded, dict):
			existing = loaded
	except (OSError, TypeError, ValueError):
		existing = {}
	existing["version"] = 1
	existing[key] = go_state
	temporary = path.with_name(path.name + ".tmp")
	with open(temporary, "w", encoding="utf-8") as file:
		json.dump(existing, file, sort_keys=True)
		file.write("\n")
	os.replace(temporary, path)

def update_day_state(state_path, go, now, key="go", day_used=None):
	"""The reading today is measured against, persisted for the next run.

	The provider has no daily history, so the first successful read of a new
	UTC day becomes the baseline; usage between midnight and that read counts
	as the previous day. A missing baseline for the current day is filled the
	same way, so a cold start does not leave `today` unavailable. A new paid
	period or a meter that fell restarts the day at the current reading.

	`day_used` is for a source that can report the day's spend from history —
	Cursor's message log has the timestamps. The baseline is then derived from
	that spend rather than from the first reading, so a late first read, a
	restart or a baseline written by an earlier version cannot lose the day.
	Without a `state_path` the baseline is computed and returned but not saved.
	"""
	if go["state"] != "ok":
		return None
	stored = _load_day_state(state_path, key)
	utc = now.astimezone(datetime.timezone.utc)
	today = utc.date().isoformat()
	last_used = _number(stored.get("last_used"))
	baseline = _number(stored.get("day_start_used")) if stored.get("day") == today else None
	if day_used is not None:
		baseline = max(0, go["used"] - max(0, int(day_used)))
	elif stored.get("period_start") != go["period_start"]:
		# The provider reset the monthly meter. Keep the day continuous by
		# carrying the pre-reset spend into the new baseline, so today's share
		# does not jump back to zero in the middle of the day.
		if baseline is not None and last_used is not None:
			baseline -= last_used
		else:
			baseline = None
	elif last_used is not None and go["used"] < last_used:
		baseline = None
	if baseline is None:
		baseline = go["used"]
	state = {
		"day": today,
		"day_start_used": baseline,
		"last_used": go["used"],
		"last_seen": int(now.timestamp()),
		"period_start": go["period_start"],
	}
	for field in ("limit", "period_end", "period_days", "period_length", "product"):
		if field in stored and field not in state:
			state[field] = stored[field]
	if state_path is not None:
		try:
			_write_day_state(state_path, state, key)
		except (OSError, TypeError, ValueError):
			pass
	return baseline

def sample_quota(now=None, state_path=None, fetch=None, db_path=None, cursor_config=None, cursor_db_path=None):
	"""All quotas at one instant, with the day baselines updated.

	A failed source becomes `unavailable`; it never raises, so the tables
	always render.
	"""
	if now is None:
		now = datetime.datetime.now().astimezone()
	read = fetch or http_get_json
	credentials = read_credentials(db_path)
	go = go_quota(credentials["go"], now, read)
	openrouter = openrouter_quota(credentials["openrouter"], read)
	state_path = state_path or STATE_PATH
	cursor = cursor_quota(
		now=now,
		db_path=cursor_db_path or db_path,
		config=cursor_config,
		state_path=state_path,
	)
	go_baseline = update_day_state(state_path, go, now, key="go") if go["state"] == "ok" else None
	if cursor.get("state") == "ok":
		cursor_baseline = cursor.get("day_start_used")
		pace_source = cursor
		pace_baseline = cursor_baseline
	else:
		pace_source = go
		pace_baseline = go_baseline
	pace = compute_pace(pace_source, pace_baseline, now) if pace_source.get("state") == "ok" else {
		"used_percent": None, "overall": None, "today": None, "days_left": None,
	}
	# Each source carries its own pace/today for display.
	go_pace = compute_pace(go, go_baseline, now) if go["state"] == "ok" else None
	cursor_pace = compute_pace(cursor, cursor.get("day_start_used"), now) if cursor.get("state") == "ok" else None
	cursor_pool_source = None
	other_pool_source = None
	if cursor.get("state") == "ok":
		cursor_pool_source = dict(cursor)
		cursor_pool_source["used"] = cursor.get("cursor_used", cursor.get("used", 0))
		cursor_pool_source["limit"] = cursor.get("limit")
		other_pool_source = dict(cursor)
		other_pool_source["used"] = cursor.get("other_used", 0)
		other_pool_source["limit"] = cursor.get("limit")
	cursor_pool_pace = compute_pace(cursor_pool_source, cursor.get("cursor_day_start_used"), now) if cursor_pool_source is not None else None
	other_pool_pace = compute_pace(other_pool_source, cursor.get("other_day_start_used"), now) if other_pool_source is not None else None
	return {
		"go": go,
		"cursor": cursor,
		"openrouter": openrouter,
		"pace": pace,
		"go_pace": go_pace,
		"cursor_pace": cursor_pace,
		"cursor_pool_pace": cursor_pool_pace,
		"other_pool_pace": other_pool_pace,
		"now": now,
	}

def _dollars(microcents, exact=False):
	"""Microcents as dollars; an exact integral amount has no decimals."""
	if exact and microcents % MICROCENTS_PER_DOLLAR == 0:
		return f"${microcents // MICROCENTS_PER_DOLLAR}"
	return f"${microcents / MICROCENTS_PER_DOLLAR:.2f}"

def _percent(value):
	return f"{round(value)}%" if value is not None else "?"

def _days_left_for(quota, go=None):
	"""The precomputed day count for a Go source, from any place it was stored."""
	if go is None:
		go = (quota or {}).get("go") or {}
	pace = (quota or {}).get("pace") or {}
	value = go.get("days_left")
	if value is None:
		value = pace.get("days_left")
	if value is None and isinstance(go.get("end"), datetime.datetime):
		value = _days_left(go.get("end"), (quota or {}).get("now"))
	return value

def _go_variants(quota, source=None, pace=None, abbreviated=True):
	"""The Go field, longest first: limit, then used, then the percentage alone."""
	if source is None:
		source = (quota or {}).get("go") or {}
	if source.get("state") != "ok":
		return []
	if pace is None:
		pace = (quota or {}).get("go_pace") or (quota or {}).get("pace") or {}
	label = "G+" if source.get("product") == "go-plus" else "G"
	if not abbreviated:
		label = "Go+" if source.get("product") == "go-plus" else "Go"
	used = _dollars(source["used"])
	limit = _dollars(source["limit"], exact=True)
	if abbreviated:
		limit = limit[1:]
	percent = _percent(pace.get("used_percent") if isinstance(pace, dict) else None)
	days = _days_left_for(quota, source) if quota is not None else source.get("days_left")
	suffix = f" ({days}d left)" if days is not None else ""
	return [
		f"{label} {used}/{limit} {percent}{suffix}",
		f"{label} {used}/{limit} {percent}",
		f"{label} {used} {percent}",
		f"{label} {percent}",
	]

def _cursor_variants(quota, source=None, pace=None, abbreviated=True, kind="cursor"):
	"""The Cursor field, longest first, mirroring Go."""
	if source is None:
		source = (quota or {}).get("cursor") or {}
	if source.get("state") != "ok":
		return []
	if pace is None:
		pace = (quota or {}).get("cursor_pace") or (quota or {}).get("pace") or {}
	if kind == "cursor":
		label = "C" if abbreviated else "Cursor"
	else:
		label = "C/o" if abbreviated else "Cursor/other"
	used = _dollars(source["used"])
	limit = _dollars(source["limit"], exact=True)
	if abbreviated:
		limit = limit[1:]
	percent = _percent(pace.get("used_percent") if isinstance(pace, dict) else None)
	days = source.get("days_left")
	if days is None and quota is not None:
		days = _days_left_for(quota, source)
	suffix = f" ({days}d left)" if days is not None else ""
	return [
		f"{label} {used}/{limit} {percent}{suffix}",
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
		days = _days_left_for(quota, go)
		day_suffix = f" ({days}d left)" if days is not None else ""
		fields.append(f"{label} {used}/{limit} {_percent(pace.get('used_percent'))}{day_suffix}")
		if pace.get("overall") is not None:
			fields.append(f"p {round(pace['overall'])}" if abbreviated else f"pace {round(pace['overall'])}%/d")
		if pace.get("today") is not None:
			fields.append(f"t {round(pace['today'])}" if abbreviated else f"today {round(pace['today'])}%")
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

def _quota_text(title, fields, width):
	"""The title and the field block, with the block against the right edge.

	The gap after the title absorbs the spare columns, so the quota reads as
	a separate block rather than as part of the `=== Skynet ===` title. A
	candidate that does not fit keeps the minimum one-space gap and is
	rejected by the caller on its length.
	"""
	if not fields:
		return title
	block = " · ".join(fields)
	if len(title) + 1 + len(block) > width:
		return title + " " + block
	return title + " " * (width - len(title) - len(block)) + block

def _source_fields(source, pace, abbreviated, primary, kind):
	"""The field list for one cost source, in display order."""
	fields = []
	if source.get("state") == "ok":
		if kind == "go":
			label = ("G+" if source.get("product") == "go-plus" else "G") if abbreviated else ("Go+" if source.get("product") == "go-plus" else "Go")
		elif kind == "cursor":
			label = "C" if abbreviated else "Cursor"
		else:
			label = "C/o" if abbreviated else "Cursor/other"
		used = _dollars(source["used"])
		limit = _dollars(source["limit"], exact=True)
		if abbreviated:
			limit = limit[1:]
		if isinstance(pace, dict):
			used_percent = pace.get("used_percent")
		else:
			used_percent = None
		if used_percent is None and source.get("state") == "ok":
			source_limit = source.get("limit") or 0
			if source_limit > 0:
				used_percent = source.get("used", 0) / source_limit * 100
		percent = _percent(used_percent)
		days = source.get("days_left")
		if days is None:
			days = _days_left_for({"go": source, "pace": pace or {}}, source) if kind == "go" else None
		suffix = f" ({days}d left)" if days is not None else ""
		fields.append(f"{label} {used}/{limit} {percent}{suffix}")
		if primary and isinstance(pace, dict):
			if pace.get("overall") is not None:
				fields.append(f"p {round(pace['overall'])}" if abbreviated else f"pace {round(pace['overall'])}%/d")
			if pace.get("today") is not None:
				fields.append(f"t {round(pace['today'])}" if abbreviated else f"today {round(pace['today'])}%")
			else:
				fields.append("t ?" if abbreviated else "today ?")
	elif source.get("state") == "unavailable":
		if kind == "go":
			fields.append("G ?" if abbreviated else "Go ?")
		else:
			fields.append("C ?" if abbreviated else "Cursor ?")
	return fields

def _or_fields(source, abbreviated):
	"""The OpenRouter field list."""
	fields = []
	if source.get("state") == "ok":
		fields.append(f"OR {source['used']}/{source['limit']}")
	elif source.get("state") == "unavailable":
		fields.append("OR ?")
	return fields

def _fit_source(title, full, abbr, variants, width):
	"""Pick the field list that fits, trying full, abbreviated, drops, variants."""
	if title is not None:
		if full and len(_quota_text(title, full, width)) <= width:
			return full, True
		if abbr and len(_quota_text(title, abbr, width)) <= width:
			return abbr, True
		fields = list(abbr)
		while fields:
			if len(_quota_text(title, fields, width)) <= width:
				return fields, True
			fields.pop()
		for variant in variants or []:
			if len(_quota_text(title, [variant], width)) <= width:
				return [variant], True
		return [], True
	block = " · ".join(full)
	if full and len(block) <= width:
		return full, False
	block = " · ".join(abbr)
	if abbr and len(block) <= width:
		return abbr, False
	fields = list(abbr)
	while fields:
		block = " · ".join(fields)
		if len(block) <= width:
			return fields, False
		fields.pop()
	for variant in variants or []:
		if len(variant) <= width:
			return [variant], False
	return [], False

def quota_line(quota, width):
	"""The cost-tracking section: one line per source, starting on the Skynet title.

	The first source that fits shares the `=== Skynet ===` title line, right-
	aligned as before; the remaining sources follow on their own lines. `None`
	gives the bare title.
	"""
	title = f"=== {NAME} ==="
	if quota is None:
		return title if len(title) <= width else title[:width]
	go = (quota or {}).get("go") or {"state": "absent"}
	cursor = (quota or {}).get("cursor") or {"state": "absent"}
	openrouter = (quota or {}).get("openrouter") or {"state": "absent"}
	pace_all = (quota or {}).get("pace") or {}
	primary = "cursor" if cursor.get("state") == "ok" else "go"
	go_pace = (quota or {}).get("go_pace")
	if go_pace is None and primary == "go":
		go_pace = pace_all
	cursor_pace = (quota or {}).get("cursor_pace")
	if cursor_pace is None and primary == "cursor":
		cursor_pace = pace_all

	sources = []
	if go.get("state") != "absent":
		full = _source_fields(go, go_pace, False, True, "go")
		abbr = _source_fields(go, go_pace, True, True, "go")
		variants = _go_variants(quota, go, go_pace, True)
		sources.append(("go", full, abbr, variants))
	if cursor.get("state") != "absent":
		cursor_pool_source = {
			"state": "ok",
			"product": "cursor",
			"limit": cursor.get("limit"),
			"used": cursor.get("cursor_used", 0),
			"days_left": cursor.get("days_left"),
		}
		other_pool_source = {
			"state": "ok",
			"product": "cursor",
			"limit": cursor.get("limit"),
			"used": cursor.get("other_used", 0),
			"days_left": cursor.get("days_left"),
		}
		cursor_pool_pace = (quota or {}).get("cursor_pool_pace")
		other_pool_pace = (quota or {}).get("other_pool_pace")
		now = (quota or {}).get("now") or datetime.datetime.now().astimezone()
		if cursor_pool_pace is None:
			cursor_pool_pace = compute_pace(cursor_pool_source, cursor.get("cursor_day_start_used"), now)
		if other_pool_pace is None:
			other_pool_pace = compute_pace(other_pool_source, cursor.get("other_day_start_used"), now)
		full = _source_fields(cursor_pool_source, cursor_pool_pace, False, True, "cursor")
		abbr = _source_fields(cursor_pool_source, cursor_pool_pace, True, True, "cursor")
		variants = _cursor_variants(quota, cursor_pool_source, cursor_pool_pace, True, "cursor")
		sources.append(("cursor", full, abbr, variants))
		full = _source_fields(other_pool_source, other_pool_pace, False, True, "cursor_other")
		abbr = _source_fields(other_pool_source, other_pool_pace, True, True, "cursor_other")
		variants = _cursor_variants(quota, other_pool_source, other_pool_pace, True, "cursor_other")
		sources.append(("cursor_other", full, abbr, variants))
	if openrouter.get("state") != "absent":
		full = _or_fields(openrouter, False)
		abbr = _or_fields(openrouter, True)
		sources.append(("openrouter", full, abbr, []))

	lines = []
	title_used = False
	for _kind, full, abbr, variants in sources:
		use_title = not title_used
		fields, used_title = _fit_source(title if use_title else None, full, abbr, variants, width)
		if used_title and fields:
			lines.append(_quota_text(title, fields, width))
			title_used = True
		elif fields:
			block = " · ".join(fields)
			if len(block) > width:
				block = block[:width]
			lines.append(" " * (width - len(block)) + block)
		# If nothing fits, skip the line.
	if not title_used:
		if lines:
			lines.insert(0, title if len(title) <= width else title[:width])
		else:
			lines.append(title if len(title) <= width else title[:width])
	return "\n".join(lines)

# Aliases for the cost-tracking section, under the names a caller might use.
quota_lines = quota_line

# Aliases for cursor helpers, under the names a caller might use.
cursor_used = _cursor_used
to_microcents = _to_microcents
quota_block = quota_line
quota_section = quota_line
cost_section = quota_line

# The values a render needs from one assistant message, in the order `aggregate`
# unpacks them. The window filters on the `time_created` column rather than on
# the JSON copy of it: both hold the same number, but only the column is
# indexed, and a `json_extract` filter must parse every row in the table
# before it can reject one.
_STATS_FIELDS = """json_extract(data, '$.model.id'),
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
		json_extract(data, '$.error.type'),
		json_extract(data, '$.error.message'),
		json_extract(data, '$.finish'),
		session_id"""
_WINDOW_ROWS_QUERY = f"SELECT {_STATS_FIELDS} FROM session_message WHERE type = 'assistant' AND time_created >= ? ORDER BY time_created"
_WINDOW_STAMPS_QUERY = "SELECT id, time_updated FROM session_message WHERE type = 'assistant' AND time_created >= ?"
_CHANGED_ROWS_QUERY = f"SELECT id, time_updated, {_STATS_FIELDS} FROM session_message WHERE id IN "
# What a watch redraw re-reads: the messages created within this many seconds,
# and the ones that have not finished. `time_created` is indexed, but the
# `type` filter needs the row behind each index entry, so scanning the whole
# window costs a page read per message (60 ms at 62k rows in 2026-11) and has
# to grow with the database. The count over `time_created` alone is covered by
# the index and says when rows appeared or went away, and the window is
# otherwise reconciled on a timer.
_TAIL_SECONDS = 900
_RECONCILE_SECONDS = 600
_WINDOW_COUNT_QUERY = "SELECT count(*) FROM session_message WHERE time_created >= ?"
_TAIL_ROWS_QUERY = f"SELECT id, time_updated, {_STATS_FIELDS} FROM session_message WHERE type = 'assistant' AND time_created >= ? ORDER BY time_created"
# The position of `finish` in a `_STATS_FIELDS` tuple; a message without one
# may still be written.
_FINISH_INDEX = 10

def _connect():
	"""A read-only connection to the message database; nothing here writes it."""
	return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

def load_stats(limit_seconds):
	"""The window's assistant messages, oldest first."""
	cutoff = (time.time() - limit_seconds) * 1000
	conn = _connect()
	try:
		return conn.execute(_WINDOW_ROWS_QUERY, (cutoff,)).fetchall()
	finally:
		conn.close()

def _rows_by_id(conn, ids):
	"""The complete rows for `ids`, in batches small enough for SQLite's variable limit."""
	rows = []
	for start in range(0, len(ids), 500):
		batch = ids[start:start + 500]
		placeholders = ",".join("?" for _ in batch)
		rows += conn.execute(_CHANGED_ROWS_QUERY + f"({placeholders})", batch).fetchall()
	return rows

class StatsCache:
	"""The window's parsed rows, kept between watch redraws.

	A redraw used to be dominated by unpacking the message JSON, so the cache
	kept the parsed rows and re-read only the messages whose `time_updated`
	moved. Finding those by scanning the whole window now costs a page read per
	message and grows with the database, so a redraw instead re-reads the
	recently created tail and the messages that have not finished. A row is
	written once and then updated in place while it streams, so those two sets
	cover what can change; a deletion or a window slide changes the row count,
	which the indexed count sees, and that triggers a full reconcile. One more
	reconcile runs every `_RECONCILE_SECONDS` in case an old message is written
	again after it finished.

	The per-model sums are kept alongside the rows and folded as a row arrives,
	so a redraw does not re-read the window into them either.
	"""

	def __init__(self):
		self._rows = {}
		self._stamps = {}
		self._by_model = {}
		self._open = set()
		self._oldest = None
		self._window_count = None
		self._reconciled_at = 0.0

	def load(self, limit_seconds):
		"""The window's rows now, parsing only the ones new or changed since the last call."""
		cutoff = (time.time() - limit_seconds) * 1000
		conn = _connect()
		try:
			count = conn.execute(_WINDOW_COUNT_QUERY, (cutoff,)).fetchone()[0]
			if (self._window_count != count
					or time.monotonic() - self._reconciled_at >= _RECONCILE_SECONDS):
				self._reconcile(conn, cutoff)
			else:
				self._read_tail(conn, cutoff)
		finally:
			conn.close()
		self._window_count = count
		self._drop_expired(cutoff / 1000)
		return list(self._rows.values())

	def stats(self):
		"""The window's per-model sums, kept current as rows arrive and leave."""
		return self._by_model

	def _remember(self, message_id, row):
		"""Put a parsed row in the cache and fold it into its model's sums."""
		if message_id in self._rows:
			self._forget(message_id)
		self._rows[message_id] = row
		stats = self._by_model.get(row[0])
		if stats is None:
			stats = _stats_entry(time.time())
			self._by_model[row[0]] = stats
		_fold_row(stats, row, 1)
		if row[_FINISH_INDEX] is None:
			self._open.add(message_id)
		if self._oldest is None or row[1] < self._oldest:
			self._oldest = row[1]

	def _forget(self, message_id):
		"""Drop a row from the cache and subtract it from its model's sums."""
		row = self._rows.pop(message_id, None)
		if row is None:
			return
		self._open.discard(message_id)
		stats = self._by_model.get(row[0])
		if stats is None:
			return
		_fold_row(stats, row, -1)
		if _is_refusal(row[8], row[9]) and stats["last_refusal"] == row[1]:
			remaining = [other[1] for other in self._rows.values()
				if other[0] == row[0] and _is_refusal(other[8], other[9])]
			stats["last_refusal"] = max(remaining, default=0)

	def _drop_expired(self, cutoff):
		"""Forget the rows that have slid out of the window."""
		if self._oldest is None or self._oldest >= cutoff:
			return
		for message_id in [message_id for message_id, row in self._rows.items()
				if row[1] < cutoff]:
			self._forget(message_id)
		self._oldest = min((row[1] for row in self._rows.values()), default=None)

	def _reconcile(self, conn, cutoff):
		"""Re-read the window's change stamps, and forget the rows that are gone."""
		stamps = dict(conn.execute(_WINDOW_STAMPS_QUERY, (cutoff,)))
		changed = [message_id for message_id, stamp in stamps.items()
			if self._stamps.get(message_id) != stamp]
		for message_id, stamp, *row in _rows_by_id(conn, changed):
			self._remember(message_id, tuple(row))
			self._stamps[message_id] = stamp
		for message_id in [message_id for message_id in self._rows
				if message_id not in stamps]:
			self._forget(message_id)
		self._stamps = dict(stamps)
		self._reconciled_at = time.monotonic()

	def _read_tail(self, conn, cutoff):
		"""Re-read the recently created rows and the messages still being written."""
		since = max(cutoff, (time.time() - _TAIL_SECONDS) * 1000)
		fetched = conn.execute(_TAIL_ROWS_QUERY, (since,)).fetchall()
		seen = {message_id for message_id, *_rest in fetched}
		fetched += _rows_by_id(conn, [message_id for message_id in self._open
			if message_id not in seen])
		for message_id, stamp, *row in fetched:
			if self._stamps.get(message_id) == stamp:
				continue
			self._remember(message_id, tuple(row))
			self._stamps[message_id] = stamp

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

def _stats_entry(now):
	"""A model's sums, empty."""
	return {
		"msgs": 0, "input": 0, "output": 0, "total": 0,
		"reasoning": 0, "cache_read": 0, "cache_write": 0,
		"refusals": 0, "last_refusal": 0,
		"finish_stop": 0, "finish_tool_calls": 0, "finish_length": 0, "finish_unknown": 0,
		"other_errors": 0, "last_other_error": 0,
		"first_seen": now, "last_seen": 0,
	}

def _is_refusal(error_type, error_message):
	"""Whether one message row is a refusal: aborted, or a rate-limit error."""
	return (
		error_type == "aborted"
		or (error_type == "provider.error"
			and "rate limit" in (error_message or "").lower())
	)

def _fold_row(stats, row, sign):
	"""Add (`sign` 1) or remove (`sign` -1) one message from a model's sums.

	The counts and token sums are exact in both directions. The two `last_*`
	maxima are only raised here; the caller lowers them when the row that held
	the maximum goes away, because the remaining rows are its to know.
	"""
	(model, created, token_in, token_out, token_total,
	 token_reasoning, cache_read, cache_write,
	 error_type, error_message, finish, session_id) = row
	stats["msgs"] += sign
	for key, value in (("input", token_in), ("output", token_out),
			("total", token_total), ("reasoning", token_reasoning),
			("cache_read", cache_read), ("cache_write", cache_write)):
		if value is not None:
			stats[key] += sign * int(value)
	if sign > 0:
		stats["first_seen"] = min(stats["first_seen"], created)
		stats["last_seen"] = max(stats["last_seen"], created)
	if _is_refusal(error_type, error_message):
		stats["refusals"] += sign
		if sign > 0:
			stats["last_refusal"] = max(stats["last_refusal"], created)
	elif error_type is not None:
		stats["other_errors"] += sign
		if sign > 0:
			stats["last_other_error"] = max(stats["last_other_error"], created)
	if finish == "stop":
		stats["finish_stop"] += sign
	elif finish == "tool-calls":
		stats["finish_tool_calls"] += sign
	elif finish == "length":
		stats["finish_length"] += sign
	elif finish == "unknown":
		stats["finish_unknown"] += sign

def aggregate(rows, now):
	"""Per-model sums over `rows`, keyed by model id."""
	by_model = {}
	for row in rows:
		model = row[0]
		stats = by_model.get(model)
		if stats is None:
			stats = _stats_entry(now)
			by_model[model] = stats
		_fold_row(stats, row, 1)
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

def section_allowances(height, today_count, window_count, overhead=6):
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
	budget = max(height - overhead, 0)
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

def render(rows, now, height=None, width=None, quota=None, by_model=None):
	"""The whole display: the header, then the Today table and the Window table.

	`height` is the number of lines the display may use, and `width` the
	columns it may use; the caps on the rows come from the first, the columns
	and the model names from the second, so the render fits the pane it has.
	`quota` is a `sample_quota` result; without one the header is unchanged.
	`by_model` is the window's sums when the caller already has them (the watch
	keeps them current); without one they are aggregated from `rows`.
	"""
	if height is None or width is None:
		size = terminal_size()
		if height is None:
			height = size.lines
		if width is None:
			width = size.columns
	all_stats = by_model if by_model is not None else aggregate(rows, now)
	local_midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
	today_cutoff = local_midnight.timestamp()
	today_rows = [(m, c, ti, to, tt, tr, cr, cw, s, en, f, sid)
		for m, c, ti, to, tt, tr, cr, cw, s, en, f, sid in rows if c >= today_cutoff]
	today_stats = aggregate(today_rows, now)
	today_count = len(used_models(today_stats))
	window_count = len(used_models(all_stats))
	quota_text = quota_line(quota, width)
	overhead = 5 + len(quota_text.splitlines())
	if height < overhead:
		# The sections need their lines before they can say anything at
		# all, and a pane shorter than that gets the counts instead: a
		# truncated table must never be mistaken for the whole truth.
		if not today_count and not window_count:
			return f"{NAME}: no agents active"
		return f"{NAME}: {plural(today_count, 'model')} today, {plural(window_count, 'model')} in window"
	if not all_stats:
		return f"{quota_text}\n\nno agents active in window"
	columns, col_w = fit_columns(width, SHOW_EXTRA)
	today_title = "=== Models (Today) ==="
	window_title = "=== Models (Window) ==="
	# A title that no longer fits gives way to the short name; the column
	# labels ride on the same line and are worth more than the brackets.
	if len(today_title) > col_w:
		today_title = "Today"
	if len(window_title) > col_w:
		window_title = "Window"
	today_allowance, window_allowance = section_allowances(height, today_count, window_count, overhead)
	today_cap = row_cap(today_count, today_allowance)
	window_cap = row_cap(window_count, window_allowance)
	today_text = render_table(today_stats, now, show_tokens=True, col_w=col_w, show_extra=SHOW_EXTRA, max_models=today_cap, title=today_title, columns=columns)
	window_text = render_table(all_stats, now, show_tokens=True, col_w=col_w, show_extra=SHOW_EXTRA, max_models=window_cap, title=window_title, columns=columns)
	return (
		f"{quota_text}\n"
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

def build_report(window_hours, now, height=None, width=None, quota=None, cache=None):
	"""The whole display; `cache` keeps the watch from re-reading the window each frame."""
	if cache is None:
		return render(load_stats(window_hours * 3600), now, height, width, quota)
	return render(cache.load(window_hours * 3600), now, height, width, quota, cache.stats())

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

def _db_changed(watcher, stamp, timeout=_POLL_SECONDS):
	"""Whether the database itself changed since `stamp`.

	An inotify wakeup is only a hint. SQLite opens and closes the WAL and the
	shared-memory file beside the database for a read-only query, and those
	opens are `IN_CLOSE_WRITE` events on names that look like the database —
	so trusting the event makes the tool wake itself forever. The mtimes are
	what decide: a read leaves them alone.
	"""
	if watcher is not None:
		if not watcher.read(timeout):
			return stamp, False
	else:
		time.sleep(timeout)
	current = db_stamp()
	return current, current != stamp

def watch(window_hours):
	with _fullscreen():
		quota = sample_quota()
		quota_due = time.monotonic() + QUOTA_REFRESH_SECONDS
		cache = StatsCache()
		draw(build_report(window_hours, time.time(), quota=quota, cache=cache))
		# The terminal's size is part of what is watched: a pane that was resized
		# has to redraw, or the old layout stays and runs off the edge. The pace
		# also changes with time, so the quota timer wakes the loop even when the
		# database does not.
		size = terminal_size()
		watcher = _db_watcher()
		stamp = db_stamp()
		last_draw = time.monotonic()
		dirty = False
		try:
			while True:
				stamp, changed = _db_changed(watcher, stamp)
				dirty = dirty or changed
				refresh_quota = time.monotonic() >= quota_due
				current_size = terminal_size()
				if not dirty and not refresh_quota and current_size == size:
					continue
				# A write is a hint that another may follow; wait out the floor so
				# a burst becomes one frame. A resize is drawn at once, and so is a
				# quota refresh that is already due.
				if current_size == size:
					wait = _REDRAW_FLOOR_SECONDS - (time.monotonic() - last_draw)
					if wait > 0:
						time.sleep(wait)
				if refresh_quota:
					quota = sample_quota()
					quota_due = time.monotonic() + QUOTA_REFRESH_SECONDS
				size = terminal_size()
				# The stamp is taken before the read, so a write during the draw
				# wakes the next frame instead of being missed.
				stamp = db_stamp()
				draw(build_report(window_hours, time.time(), quota=quota, cache=cache))
				last_draw = time.monotonic()
				dirty = False
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
