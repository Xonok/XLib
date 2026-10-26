"""Model transports. Two paths, measured 2026-09-27 (see plans/model-benchmark.md §0.3).

	http	direct OpenAI-compatible request. ~0 overhead, sub-second. OpenRouter :free
			models, and space-bunny-free via the Zen gateway.
	harness	`opencode run`. ~13,140 prompt tokens and ~11.5s per call, of which ~13k is
			opencode's own fixed preamble — it does not shrink when the agent is stripped
			of tools, so there is no way to trim it. 87x the cost of http.

The two providers disagree on the reasoning field name (OpenRouter sends `reasoning`,
Zen sends `reasoning_content`); everything downstream needs one name, so it is
normalised here rather than at each call site.

Google's own route is the third direct backend. It is reached on the same
OpenAI-compatible path as the others, and it meters **per model** — 15 requests a
minute for the flash-lite family, 16,000 input tokens a minute for gemma-4-26b, both
measured 2026-10-22. The limit is carried by the registry entry and enforced by
`_pace`, because a quota refusal that is not paced for turns a two-second wait into
a lost cell.
"""

import json,os,re,subprocess,time,urllib.error,urllib.request

AUTH_PATH = os.path.expanduser("~/.local/share/opencode/auth.json")
HARNESS_TIMEOUT = 900
# Direct HTTP gets its own, much shorter timeout. It inherited HARNESS_TIMEOUT because there
# was only one default, which is fine for a whole opencode session and absurd for a single
# free-model completion: one hung model then cost 900s x 3 retries = 45 minutes of a run
# that could never produce a result. Observed 2026-09-27 on north-mini-code, which returns
# empty content with finish_reason='error' and then holds the socket open.
HTTP_TIMEOUT = 180
RETRY_STATUS = {429,500,502,503,504}

class TransportError(Exception):
	"""A call that produced no reply.

	`body` is the provider's whole error body when there was one. It used to be cut to
	200 characters for the message and dropped afterwards, and the part that says
	*which* quota was exceeded begins after that cut — so a per-minute refusal and a
	per-day one arrived as the same string, and a wave deferred a model for the day over
	a wait that clears in two seconds (E31, measured 2026-10-22).
	"""
	def __init__(self,message,body=None,status=None,quota=None):
		super().__init__(message)
		self.body = body
		self.status = status
		self.quota = quota or {}

class UnseenShape(Exception):
	"""An event or a field arrived in a shape this tool does not know.

	The human's pattern, stated 2026-10-20: make a branch for each known case and add an
	else for "something weird happened that I didn't foresee", so that a change outside
	our control becomes a first-class error that is clearly separate from the ordinary
	functioning of the code. Here that means a hole in a run rather than a number that
	looks like a measurement and is not.
	"""

# The console's own gateway is reached in opencode's namespace. The registry's
# `provider` is a backend, and the two are not the same thing.
CONSOLE_NAMESPACE = "opencode"

def route_of(model):
	"""The `provider/model` route to ask opencode for.

	The registry's `provider` is the backend. The console's Zen gateway is reached as
	`opencode/<id>`; an OpenRouter model is reached as `openrouter/<vendor>/<model>`. A
	hardcoded `opencode/{id}` therefore asked for a route that does not exist for most
	of the registry, and the answer was `provider.no-route` — which reads like a model
	that cannot answer, and was recorded as one. It is why a model the human cared most
	about read as "unmeasurable" for a month.
	"""
	namespace = model.get("namespace") or model.get("provider") or ""
	if namespace == "zen":
		namespace = CONSOLE_NAMESPACE
	if not namespace:
		raise TransportError(f"{model.get('id')}: no provider, so there is no route to ask for")
	return f"{namespace}/{model['id']}"

def token_total(part):
	"""The session's token total, wherever this opencode version keeps it.

	opencode 1 put it at `part.tokens.total`. opencode 2 dropped that field and carries
	the components instead, so reading `total` alone gave every harness run a token count
	of zero — and a run that looks free was not. That is E12's defect class returning
	under the upgrade.
	"""
	tok = (part or {}).get("tokens") or {}
	total = tok.get("total")
	if isinstance(total,int):
		return total
	cache = tok.get("cache") or {}
	parts = [tok.get("input"),tok.get("output"),tok.get("reasoning"),cache.get("read"),cache.get("write")]
	if not any(isinstance(p,int) for p in parts):
		return None
	return sum(p for p in parts if isinstance(p,int))

def _openrouter_key():
	# Read lazily and never log it: a benchmark run writes every prompt to disk.
	with open(AUTH_PATH) as f:
		return json.load(f)["openrouter"]["key"]

def _google_key():
	"""Google's API key, from the same auth store opencode's `/connect` writes.

	Read lazily and never log it: a benchmark run writes every prompt to disk. A missing
	key is a transport error with a fix in it rather than a bare KeyError, because a run
	that dies on `KeyError: 'google'` says nothing about what to do.
	"""
	try:
		with open(AUTH_PATH) as f:
			return json.load(f)["google"]["key"]
	except (OSError,KeyError,ValueError) as e:
		raise TransportError(f"no Google API key in {AUTH_PATH} ({type(e).__name__}); "
			"connect it with `opencode auth login`") from e

def _post(url,payload,headers,timeout):
	body = json.dumps(payload).encode()
	# Cloudflare sits in front of the Zen gateway and rejects urllib's default
	# User-Agent with "error code: 1010" (observed 2026-09-27). curl is not blocked, so
	# every probe made with curl passed while every Python call failed — which looks
	# exactly like a rate limit. Send an ordinary client UA.
	all_headers = {"Content-Type":"application/json","User-Agent":"opencode-model-bench/1.0",**headers}
	req = urllib.request.Request(url,data=body,headers=all_headers)
	with urllib.request.urlopen(req,timeout=timeout) as r:
		raw = r.read()
		return json.loads(raw),raw.decode("utf-8","replace")

def _auth_headers(model):
	"""The auth a direct provider needs, and an error for one this tool does not know.

	A provider with no branch used to go out unauthenticated and come back 401, which
	reads as a wrong key rather than as a route the tool has never had — the same shape
	as the missing Google route that left the corpus's largest hole (SBEA654).
	"""
	provider = model.get("provider")
	if provider == "openrouter":
		return {"Authorization":f"Bearer {_openrouter_key()}","X-Title":"model-bench"}
	if provider == "google":
		# The OpenAI-compatible endpoint takes the API key as a bearer token. The key is
		# in opencode's own auth store, beside OpenRouter's, so connecting a provider is
		# one `/connect` and no file outside it.
		return {"Authorization":f"Bearer {_google_key()}"}
	if provider == "zen":
		# space-bunny is reachable unauthenticated by design; every other console model
		# is harness-only and never reaches the direct path.
		return {}
	raise UnseenShape(f"{model.get('id')}: no auth path for provider {provider!r}")

def _error_body(e):
	"""The provider's whole error body. Never a prefix: the quota is at the end."""
	try:
		return e.read().decode("utf-8","replace")
	except Exception:
		return ""

def parse_quota(body):
	"""The provider's own account of a refusal, out of the body it sent.

	Google's OpenAI-compatible path wraps the error in a one-element **list**; the
	native path uses an object. Read both rather than the shape that happened to be
	measured first. The fields kept are the ones that tell a minute quota from a day's:
	the metric, the id, the value, and the wait the provider names. Measured
	2026-10-22: `quotaId` `GenerateRequestsPerMinutePerProjectPerModel-FreeTier`,
	`quotaValue` `15`, `RetryInfo.retryDelay` **1s on one run and 47s on the next**
	(the window slides).
	"""
	out = {}
	try:
		data = json.loads(body or "")
	except (TypeError,ValueError):
		return out
	if isinstance(data,list):
		data = data[0] if data else {}
	if not isinstance(data,dict):
		return out
	err = data.get("error")
	if not isinstance(err,dict):
		return out
	out["message"] = err.get("message") or ""
	out["status"] = err.get("status") or ""
	for detail in err.get("details") or []:
		if not isinstance(detail,dict):
			continue
		kind = detail.get("@type") or ""
		if kind.endswith("QuotaFailure"):
			violations = detail.get("violations") or []
			if violations and isinstance(violations[0],dict):
				v = violations[0]
				out["quota_metric"] = v.get("quotaMetric")
				out["quota_id"] = v.get("quotaId")
				out["quota_value"] = v.get("quotaValue")
		elif kind.endswith("RetryInfo"):
			out["retry_delay"] = _delay_seconds(detail.get("retryDelay"))
	if "retry_delay" not in out:
		# Some refusals name the wait only in prose: "Please retry in 47.745831562s."
		out["retry_delay"] = _retry_from_message(out.get("message") or "")
	return out

def _delay_seconds(text):
	"""`"47s"` / `"1.895382928s"` → seconds, or None when the provider named none."""
	if not isinstance(text,str):
		return None
	m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)s\s*$",text)
	return float(m.group(1)) if m else None

def _retry_from_message(message):
	m = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s",message or "",re.I)
	return float(m.group(1)) if m else None

def _refusal_text(model,status,body,quota):
	"""One line that names the refusal, with the quota and the wait when they exist."""
	text = f"{model['id']}: HTTP {status}"
	if quota.get("quota_id"):
		text += f" {quota['quota_id']}={quota.get('quota_value')}"
	if quota.get("retry_delay") is not None:
		text += f" retry in {quota['retry_delay']:.1f}s"
	else:
		text += f" {(quota.get('message') or body or '')[:120]}"
	return text

_pace_state = {}

def _input_tokens(messages):
	"""A conservative estimate of one call's input tokens.

	The provider counts its own tokens, which a caller cannot know before the call.
	Three characters per token over-counts prose; the margin is deliberate, because
	over-pacing costs wall clock and under-pacing costs a 429 and a lost cell.
	"""
	return max(1,sum(len(m.get("content") or "") for m in (messages or []))//3)

def _pace(model,tokens):
	"""Wait until one more request fits inside the model's measured minute quota.

	The limit belongs to the model, not to the wave script: it is per model per project,
	and it differs by model — flash-lite 15 requests a minute, gemma-4-26b 16,000 input
	tokens a minute (both measured 2026-10-22). A per-process pacer cannot coordinate
	two processes running the same model, so a wave must not do that.
	"""
	rpm = model.get("rpm")
	tpm = model.get("tpm")
	if not rpm and not tpm:
		return
	if tpm and tokens > int(tpm):
		# One call is larger than the whole minute's allowance. No wait makes it fit;
		# the 429 branch is the backstop, and blocking the queue would only delay it.
		tpm = None
	key = model["id"]
	now = time.time()
	window = [e for e in _pace_state.get(key,[]) if now - e[0] < 60]
	while window:
		request_full = rpm and len(window) >= int(rpm)
		token_full = tpm and sum(e[1] for e in window) + tokens > int(tpm)
		if not (request_full or token_full):
			break
		wait = 60 - (now - window[0][0])
		if wait > 0:
			time.sleep(wait + 0.05)
		now = time.time()
		window = [e for e in window if now - e[0] < 60]
	window.append((now,tokens))
	_pace_state[key] = window

def _http_call(model,messages,endpoint,headers,max_tokens,temperature,timeout):
	payload = {"model":model["id"],"messages":messages,"max_tokens":max_tokens}
	if temperature is not None:
		payload["temperature"] = temperature
	data,raw = _post(f"{endpoint}/chat/completions",payload,headers,timeout)
	if "error" in data:
		raise TransportError(f"{model['id']}: {data['error'].get('message',data['error'])}")
	choice = data["choices"][0]
	msg = choice["message"]
	return {
		"text":msg.get("content") or "",
		# One name downstream. OpenRouter calls it `reasoning`, Zen `reasoning_content`.
		"reasoning":msg.get("reasoning") or msg.get("reasoning_content") or "",
		"raw_tokens":data.get("usage",{}).get("total_tokens"),
		# A reasoning model that spends its whole budget thinking returns empty content
		# with finish_reason "length". That is a budget problem, not a network failure, and
		# the two must never land in the same bucket.
		"finish_reason":choice.get("finish_reason"),
		# The provider's own response, verbatim. The text above is what the model said;
		# this is what the provider said about it — the envelope, the usage, the ids. It
		# costs a few hundred bytes and it is the raw end of the measurement, so it is
		# kept: the human's rule, 2026-10-20, is to keep as much data as possible, because
		# deciding that some of it is irrelevant is easy afterwards and impossible before.
		"raw":raw,
	}

_CLI_FLAGS = None

def cli_flags():
	"""The flags this opencode actually has, read from the binary rather than assumed.

	opencode 2 removed `--pure` and `--dir`. `--pure` prints the usage text and exits 0,
	so a command that still carried it produced no events and no error at all — a silent
	failure that reads like a model that did nothing, and that capped every harness
	model at `supervision` for a day. Reading the flags makes the tool work on either
	version instead of on one and not the other.
	"""
	global _CLI_FLAGS
	if _CLI_FLAGS is None:
		try:
			proc = subprocess.run(["opencode","run","--help"],capture_output=True,text=True,timeout=30)
			text = proc.stdout + proc.stderr
		except Exception:
			text = ""
		_CLI_FLAGS = set(re.findall(r"^\s{2,}(--[a-z][a-z-]*)",text,re.M))
	return _CLI_FLAGS

def harness_cmd(model,workdir,prompt):
	"""The `opencode run` command line for one harness session.

	Separate from the call so that what is asked for can be checked without running it —
	the route, the flags and the directory are three ways of asking for a session that
	does not exist, and only one of them says so.
	"""
	# --pure keeps external plugins out; --format json is the only format reporting usage.
	# The ~13k preamble is unavoidable, which is the whole reason this path is last.
	# Deliberately NOT --auto: auto-approving permissions would hide a model asking for
	# consent, which is behaviour worth seeing.
	#
	# The flags are asked of the binary rather than assumed: opencode 2 dropped `--pure`
	# and `--dir`, and `--pure` there prints the usage text and exits 0, so a command that
	# still carried it produced no events and no error — a silent failure that reads like
	# a model that did nothing.
	cmd = ["opencode","run","--format","json","-m",route_of(model)]
	flags = cli_flags()
	if "--pure" in flags:
		cmd.append("--pure")
	if model.get("agent"):
		# An agent definition is selected by NAME, and opencode resolves that name from
		# the session's own project directory — so the definition has to be planted in the
		# sandbox before the run, not passed on the command line. A `--agent` this opencode
		# does not have is an error and not a shrug: silently running the default agent
		# would record a row that says "arm B" and is really arm C.
		if "--agent" not in flags:
			raise TransportError(f"{model['id']}: this opencode has no --agent flag, so the "
				f"definition {model['agent']!r} cannot be selected")
		cmd += ["--agent",model["agent"]]
	if "--dir" in flags:
		cmd += ["--dir",workdir]
	cmd.append(prompt)
	return cmd

def provider_error(events):
	"""What the provider said, if it said anything.

	opencode reports a provider-side failure as an event in the stream, not on stderr:
	`{"type":"error","error":{"type":"provider.quota","message":"Rate limit exceeded..."}}`.
	**The harness mapping ignored those events**, so a session that the provider refused
	produced a record saying only `not-measurable` with an empty stderr — the reader
	could not tell a quota exhaustion from a model that refused to answer, from a
	transport that died. The explanation was in the stream the whole time.

	Measured 2026-10-20: the console's own free tier ran out mid-wave and four models'
	six runs each came back `not-measurable` with no reason at all.
	"""
	for ev in events or []:
		if ev.get("type") != "error":
			continue
		err = ev.get("error") or {}
		kind = err.get("type") or "error"
		message = err.get("message") or ""
		body = err.get("response") or {}
		if not message and isinstance(body,dict):
			message = str(body.get("body") or "")[:200]
		text = f"{kind}: {message}".strip(": ")
		if text:
			return text[:400]
	return ""

def harness_stream(model,prompt,workdir,timeout):
	"""Run one whole `opencode run` session and return its raw event list.

	Needed because a harness-transport model cannot be driven turn by turn at all: the
	`opencode run` path *is* a whole agent session, so the caller gets a finished
	transcript rather than one reply. `agent.run_episode_harness` reconstructs a trace
	from these events so every model reaches the same gates.
	"""
	cmd = harness_cmd(model,workdir,prompt)
	# opencode 2 takes the session directory from $PWD, not from the process cwd, so both
	# are set. A run that opens the wrong directory still succeeds, checks out a
	# different tree and says so in its own words — it graded `not-capable` on five turns
	# that way, and the ledger's standing audit admitted it as a result.
	env = dict(os.environ)
	env["PWD"] = workdir
	try:
		proc = subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,
			cwd=workdir,env=env)
	except subprocess.TimeoutExpired as e:
		# A timeout is a result, not a crash. The partial stream is the measurement: it
		# shows what the model did before it stopped converging, and a killed run must
		# read as "did not finish" so it fails G4 the same way a turn-capped run does.
		events = _parse_events(e.stdout or "")
		return events,{"returncode":None,"timed_out":True,"stderr":(e.stderr or "")[:400],
			"provider_error":provider_error(events),"stdout":e.stdout or ""}
	events = _parse_events(proc.stdout)
	return events,{"returncode":proc.returncode,"timed_out":False,"stderr":proc.stderr[:400],
		"provider_error":provider_error(events),"stdout":proc.stdout or ""}

def _parse_events(stdout):
	events = []
	for line in (stdout or "").splitlines():
		if not line.startswith("{"):
			continue
		try:
			events.append(json.loads(line))
		except json.JSONDecodeError:
			continue
	return events

def _harness_call(model,prompt,workdir,max_tokens,timeout):
	events,info = harness_stream(model,prompt,workdir,timeout)
	text,tokens,reasoning = "","",None
	for ev in events:
		part = ev.get("part") or {}
		if ev.get("type") == "text":
			text += part.get("text","")
		elif ev.get("type") == "reasoning":
			reasoning = (reasoning or "") + (part.get("text","") or "")
		elif ev.get("type") == "step_finish":
			# Usage is at part.tokens, not ev.tokens — reading the top level returned None
			# for every harness model, so harness runs reported zero token cost and looked
			# free. `total` is CUMULATIVE for the session, so the last one is the run's —
			# and opencode 2 dropped the field, so it is recomputed from the components.
			total = token_total(part)
			if isinstance(total,int):
				tokens = total
	return {"text":text,"reasoning":reasoning or "","raw_tokens":tokens,
		"timed_out":info["timed_out"]}

def call_chat(model,messages,workdir="/tmp/opencode/bench-run",max_tokens=2048,temperature=None,retries=3,timeout=None):
	"""One call with a full conversation. `call_model` below is the single-turn case.

	`timeout` defaults per transport, because the two are not the same kind of wait: a
	direct completion should be gone in a minute, a whole opencode session is entitled to
	several. One shared default meant a hung free model stalled a run for 45 minutes."""
	if timeout is None:
		timeout = HARNESS_TIMEOUT if model.get("transport") == "harness" else HTTP_TIMEOUT
	last = None
	for attempt in range(retries):
		try:
			if model.get("transport") == "harness":
				prompt = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
				out = _harness_call(model,prompt,workdir,max_tokens,timeout)
			else:
				headers = _auth_headers(model)
				# Pace before the call, not after: the slot the provider will count is the
				# one about to be used, and a burst that only looks at completed calls
				# still meets the wall.
				_pace(model,_input_tokens(messages))
				out = _http_call(model,messages,model["endpoint"],headers,
					max_tokens,temperature,timeout)
			if not out["text"].strip():
				# Distinguish "truncated while reasoning" from a genuine empty answer. A
				# reasoning model given too small a budget reports finish_reason "length"
				# and no content; retrying that as a transport error hides a config mistake.
				reason = out.get("finish_reason")
				raise TransportError(f"{model['id']}: empty response (finish_reason={reason!r}"
					f"{'; raise max_tokens' if reason == 'length' else ''})")
			out["transport"] = model.get("transport")
			return out
		except urllib.error.HTTPError as e:
			# 403 is ambiguous on the Zen gateway: it means both "wrong caller" and
			# "rate limited" (observed 2026-09-27 — space-bunny returned 403 mid-run, then
			# answered again seconds later). Treating every 403 as terminal drops judge
			# calls for a reason that clears on its own; treating none as terminal wastes
			# quota re-asking a model that can never answer. So read the message.
			body = _error_body(e)
			gated = "within OpenCode" in body
			quota = parse_quota(body) if e.code == 429 else {}
			last = TransportError(_refusal_text(model,e.code,body,quota),
				body=body,status=e.code,quota=quota)
			if gated or attempt == retries-1:
				raise last
			if e.code == 429 and quota.get("retry_delay") is not None:
				# The provider names the wait, and it slides: 1s on one burst, 47s on the
				# next. Retrying on our own clock lands inside the same minute window and
				# turns a two-second refusal into a lost cell (E31).
				time.sleep(quota["retry_delay"] + 0.5)
				continue
		except (TransportError,urllib.error.URLError,subprocess.TimeoutExpired) as e:
			last = e
			if attempt == retries-1:
				raise TransportError(f"{model['id']}: {e}") from e
		time.sleep(2**attempt)
	if isinstance(last,TransportError):
		raise last
	raise TransportError(str(last))

def call_model(model,prompt,**kwargs):
	"""Single-turn convenience wrapper. Present because most call sites have one prompt;
	the agent loop needs `call_chat` and passing a messages list here produced a 400
	("Input must have at least 1 token") that looked like a model fault."""
	return call_chat(model,[{"role":"user","content":prompt}],**kwargs)

REQUIRED_FIELDS = ("id","provider","transport")
VALID_TRANSPORTS = ("http","harness")

def validate_registry(registry):
	"""Fail loudly on a malformed entry. A silently broken entry does not crash — it
	benchmarks the wrong model, or nothing, and the report still looks fine. The dotted
	names in models.toml (`qwen3.8-27b`) become nested TOML tables unless quoted, which is
	exactly how two models went missing from the registry unnoticed."""
	problems = []
	for name,model in registry.items():
		for field in REQUIRED_FIELDS:
			if not model.get(field):
				problems.append(f"{name}: missing {field}")
		if model.get("transport") not in VALID_TRANSPORTS:
			problems.append(f"{name}: transport {model.get('transport')!r} not in {VALID_TRANSPORTS}")
		if model.get("transport") == "http" and not model.get("endpoint"):
			problems.append(f"{name}: http transport with no endpoint")
		for field in ("rpm","tpm"):
			value = model.get(field)
			if value is not None and (not isinstance(value,int) or value <= 0):
				problems.append(f"{name}: {field} must be a positive integer, not {value!r}")
		if "reasoning" in model and not isinstance(model["reasoning"],bool):
			problems.append(f"{name}: reasoning must be true or false, not {model.get('reasoning')!r}")
		if model.get("agent") and not model.get("agent_file"):
			problems.append(f"{name}: names the agent {model['agent']!r} but no agent_file to plant it from")
	return problems

def probe(registry):
	"""Re-verify which models actually answer right now. Free tiers get gated, renamed
	and retired without notice, so a registry entry is a claim, not a fact."""
	rows = []
	for name,model in sorted(registry.items()):
		try:
			out = call_model(model,"Reply with exactly: OK",max_tokens=4096,retries=1,timeout=90)
			rows.append((name,"open",out["transport"],out["raw_tokens"]))
		except Exception as e:
			msg = str(e)
			tag = "harness-gated" if ("agentic harness" in msg or "within OpenCode" in msg) else "upstream/other"
			rows.append((name,tag,model.get("transport",""),msg[:70]))
	return rows

if __name__ == "__main__":
	import sys,tomllib
	# Flags and the registry path were conflated: `sys.argv[1]` took "--probe" as the
	# registry filename, so the documented way to re-verify gating died on a FileNotFound
	# instead of probing. A tool you cannot run does not get re-verified, and then the
	# registry's gating column rots silently.
	args = [a for a in sys.argv[1:] if not a.startswith("-")]
	registry_path = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)),"models.toml")
	reg = tomllib.load(open(registry_path,"rb"))
	bad = validate_registry(reg)
	if bad:
		print("registry invalid:"); [print("  "+b) for b in bad]; sys.exit(1)
	print(f"{len(reg)} models, registry valid ({registry_path})\n")
	for name,status,transport,detail in probe(reg):
		print(f"  {name:24s} {status:14s} via {transport or '-':8s} {detail}")
