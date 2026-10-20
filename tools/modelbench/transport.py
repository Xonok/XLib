"""Model transports. Two paths, measured 2026-09-27 (see plans/model-benchmark.md §0.3).

	http	direct OpenAI-compatible request. ~0 overhead, sub-second. OpenRouter :free
			models, and space-bunny-free via the Zen gateway.
	harness	`opencode run`. ~13,140 prompt tokens and ~11.5s per call, of which ~13k is
			opencode's own fixed preamble — it does not shrink when the agent is stripped
			of tools, so there is no way to trim it. 87x the cost of http.

The two providers disagree on the reasoning field name (OpenRouter sends `reasoning`,
Zen sends `reasoning_content`); everything downstream needs one name, so it is
normalised here rather than at each call site.
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
	pass

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

def _post(url,payload,headers,timeout):
	body = json.dumps(payload).encode()
	# Cloudflare sits in front of the Zen gateway and rejects urllib's default
	# User-Agent with "error code: 1010" (observed 2026-09-27). curl is not blocked, so
	# every probe made with curl passed while every Python call failed — which looks
	# exactly like a rate limit. Send an ordinary client UA.
	all_headers = {"Content-Type":"application/json","User-Agent":"opencode-model-bench/1.0",**headers}
	req = urllib.request.Request(url,data=body,headers=all_headers)
	with urllib.request.urlopen(req,timeout=timeout) as r:
		return json.loads(r.read())

def _http_call(model,messages,endpoint,headers,max_tokens,temperature,timeout):
	payload = {"model":model["id"],"messages":messages,"max_tokens":max_tokens}
	if temperature is not None:
		payload["temperature"] = temperature
	data = _post(f"{endpoint}/chat/completions",payload,headers,timeout)
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
	if "--dir" in flags:
		cmd += ["--dir",workdir]
	cmd.append(prompt)
	return cmd

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
		return events,{"returncode":None,"timed_out":True,"stderr":(e.stderr or "")[:400]}
	events = _parse_events(proc.stdout)
	return events,{"returncode":proc.returncode,"timed_out":False,"stderr":proc.stderr[:400]}

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
				headers = {}
				if model["provider"] == "openrouter":
					headers = {"Authorization":f"Bearer {_openrouter_key()}","X-Title":"model-bench"}
				out = _http_call(model,messages,model["endpoint"],headers,max_tokens,temperature,timeout)
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
			body = ""
			try:
				body = e.read().decode()[:200]
			except Exception:
				pass
			gated = "within OpenCode" in body
			last = TransportError(f"{model['id']}: HTTP {e.code} {body[:120]}")
			if gated or attempt == retries-1:
				raise last
		except (TransportError,urllib.error.URLError,subprocess.TimeoutExpired) as e:
			last = e
			if attempt == retries-1:
				raise TransportError(f"{model['id']}: {e}") from e
		time.sleep(2**attempt)
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
