"""Episode runner: sets up a sandbox, drives one model through it, scores the trace.

An episode gets a fresh copy of its directory every time, so a repeat run cannot inherit
the previous run's fix. That is the whole point of repeating: whether a model finds the
bug on its own second and third attempts is part of what trust means.
"""

import argparse,agent,hashlib,json,os,shutil,subprocess,sys,tempfile,time,tomllib,trace,transport

HERE = os.path.dirname(os.path.abspath(__file__))
EPISODES = os.path.join(HERE,"episodes")
REGISTRY = os.path.join(HERE,"models.toml")

# Reasoning models spend thousands of tokens thinking before answering and return EMPTY
# content when the budget is too small (`finish_reason: length`), which reads as a model
# that cannot follow instructions. The budget is a property of the model, so it comes
# from the registry (`reasoning = true`) rather than from a list of names hard-coded in
# each wave script — that list is how a thinking model was given 4096 and graded
# `not-capable` (E23).
DEFAULT_MAX_TOKENS = 4096
REASONING_MAX_TOKENS = 12288

def budget_for(model):
	"""The per-call token budget a model needs, from the registry rather than its name."""
	return REASONING_MAX_TOKENS if model.get("reasoning") else DEFAULT_MAX_TOKENS

def load_episode(name):
	dir_path = os.path.join(EPISODES,name)
	with open(os.path.join(dir_path,"REQUEST.md")) as f:
		request = f.read()
	baseline_pass,baseline = trace.check_episode(dir_path)
	# Refuse to run an episode whose own checker disagrees with itself. Running it anyway
	# would produce grades derived from a broken instrument, and every one of them would
	# look like a finding about a model.
	if baseline.get("checker_fault"):
		faulted = [c["account"] for c in baseline["cases"] if c.get("fault")]
		raise SystemExit(f"episode {name!r} has a faulted checker on {faulted} — "
			"fix the episode's ground truth before measuring any model against it")
	return {"name":name,"dir":dir_path,"request":request,
		"baseline_pass":baseline_pass,"baseline":baseline}

def fingerprints(model,protocol=None):
	"""The fingerprints that say what this row was measured and evaluated on.

	Three, and the third is new. `bench_version` is the measurement side, `grade_version`
	the evaluation side, and `mapping_version` names the part of the measurement that is
	the mapping — the code that turns a model's output into the trace the gates read. It
	is carried in the row because a fingerprint nobody can see in the row is a fingerprint
	nobody can use: the 2026-10-20 wave's mapping marker was dropped on the way to disk
	and not one of its 55 graded harness rows carried it.
	"""
	transport_name = model.get("transport")
	return {"bench_version":agent.bench_version(transport_name,protocol=protocol),
		"grade_version":trace.grade_version(),
		"mapping_version":agent.mapping_version(transport_name),
		# Which protocol the model was shown, in the row itself. The two populations are
		# read differently on purpose - one measures compliance, one measures the habit -
		# so a reader must be able to tell them apart without opening the trace.
		"protocol":agent.protocol_label(protocol)}

def episode_hash(dir_path):
	"""A hash of one episode's files: what the model was actually asked to do.

	The record names the episode by name, and a name does not survive the episode being
	edited — `invoicer` was the same name before and after its reconciliation table was
	re-aligned. A measurement that cannot say which episode content it ran against
	cannot be compared with one that did, and the point of storing a measurement is that
	somebody can look at it later.
	"""
	h = hashlib.sha256()
	for dirpath,dirnames,files in os.walk(dir_path):
		dirnames[:] = sorted(n for n in dirnames if n != "__pycache__")
		for f in sorted(files):
			p = os.path.join(dirpath,f)
			h.update(os.path.relpath(p,dir_path).encode())
			try: h.update(open(p,"rb").read())
			except OSError: pass
	return "ep-" + h.hexdigest()[:12]

def run_once(model,episode,run_root,max_turns=agent.MAX_TURNS,max_tokens=None,protocol=None):
	"""One episode attempt in a throwaway copy of the episode directory.

	`max_tokens=None` means "whatever this model needs", read from its registry entry, so
	a caller cannot silently under-budget a thinking model. An explicit number still wins
	for an experiment that wants one.
	"""
	if max_tokens is None:
		max_tokens = budget_for(model)
	sandbox = tempfile.mkdtemp(prefix=f"ep-{episode['name']}-",dir=run_root)
	shutil.copytree(episode["dir"],sandbox,dirs_exist_ok=True)
	# REQUEST.md is the harness's, not the model's — it is what the agent loop renders into
	# the first user turn. check.py stays visible on purpose: the model is told to confirm
	# with it, so hiding it would be a lie, and it holds no secret (every expected value is
	# already in SPEC.md's reconciliation table). Error (f) — the right information in
	# context, unaccounted for — is only measurable if the information really is there.
	started = int(time.time())
	if model.get("transport") == "harness":
		raw = agent.run_episode_harness(model,episode["request"],sandbox,
			max_turns=max_turns,max_tokens=max_tokens,protocol=protocol)
	else:
		raw = agent.run_episode(model,episode["request"],sandbox,
			max_turns=max_turns,max_tokens=max_tokens)
	result = trace.analyse(raw,baseline=episode["baseline"])
	grade,failed = trace.grade(result)
	return {"episode":episode["name"],"model":model["id"],"transport":model.get("transport"),
		"sandbox":sandbox,"grade":grade,"failed_gates":failed,
		# Which measurement and which evaluation produced this. The human's rule
		# (2026-09-28): changing the benchmark invalidates earlier results and should be
		# reserved for when the benchmark is wrong, so a result has to be able to say what it
		# was measured on. The three are allowed to move at different rates: bench_*
		# changes invalidate, grade_* changes are re-derivable, and mapping_version says
		# which part of the measurement was the mapping.
		**fingerprints(model,protocol=protocol),
		# When it ran, and under what settings. A measurement without a timestamp cannot
		# be placed, and a measurement without its settings cannot be reproduced — and
		# the point of keeping a measurement is that somebody can build a benchmark over
		# it later, which needs both.
		"started":started,"ended":int(time.time()),
		"settings":{"model":model.get("id"),"provider":model.get("provider"),
			"namespace":model.get("namespace"),"endpoint":model.get("endpoint"),
			"agent":model.get("agent"),"max_turns":max_turns,"max_tokens":max_tokens},
		"episode_hash":episode_hash(episode["dir"]),
		# The raw turns are KEPT. analyse() reads them, so a new gate used to cost a
		# re-measurement — which is how six criterion changes in one day turned into
		# discarded runs. With them in the record, evaluation can be re-derived offline and
		# measurement stops being repeated for the sake of a scoring change.
		#
		# And the rest of the measurement: what the model was asked, the provider's own
		# response, the session's raw output. **This is the measurement layer, and it is
		# meant to stand on its own** — a benchmark can be constructed later over the
		# stored measurements, which is only possible if the measurement says what it was
		# asked, what came back, and under what settings.
		"trace":{"turns":raw.get("turns",[]),"finished":raw.get("finished"),
			"claim":raw.get("claim"),"status":raw.get("status"),
			"n_turns":raw.get("n_turns"),"usage":raw.get("usage"),
			"protocol":raw.get("protocol"),
			"prompt":raw.get("prompt"),"messages":raw.get("messages"),
			"raw":raw.get("raw"),"session":raw.get("session")},
		# The confounds of the harness path travel with the result, so a report cannot
		# quote a harness grade beside a direct grade without the difference showing.
		# The provider's own explanation of a failed session, and the process's stderr.
		# Without these a refused run says only "not-measurable", and a reader cannot
		# tell a quota exhaustion from a model that would not answer.
		"provenance":{"transport":raw.get("transport","four-tool"),
			"timed_out":raw.get("timed_out"),"turn_budget":raw.get("turn_budget"),
			"over_budget":raw.get("over_budget"),
			"provider_error":raw.get("provider_error",""),"stderr":raw.get("stderr","")},
		**result}

def main():
	p = argparse.ArgumentParser(description="Run agentic benchmark episodes")
	p.add_argument("--model",required=True)
	p.add_argument("--episode",action="append",help="repeatable; default = all")
	p.add_argument("--repeats",type=int,default=3)
	p.add_argument("--max-turns",type=int,default=agent.MAX_TURNS)
	# Past this only to override what the registry says a model needs; the default is
	# `None`, resolved per model by `budget_for`. Reasoning-heavy models spend thousands
	# of tokens thinking before answering and return EMPTY content when truncated
	# (finish_reason=length). In a 12-turn episode that is a budget problem masquerading
	# as a model that cannot follow instructions.
	p.add_argument("--max-tokens",type=int,default=None,
		help="override the registry-derived per-call budget (default: the model's own)")
	p.add_argument("--out",required=True)
	p.add_argument("--registry",default=REGISTRY)
	p.add_argument("--keep-sandbox",action="store_true")
	# Which protocol the model is shown. The default is the one the corpus was
	# measured under; the other one exists so the compliance question can be measured
	# both ways rather than argued.
	p.add_argument("--protocol",choices=("asked","unasked"),default="asked",
		help="asked: the protocol that asks for the verification (the default). "
			"unasked: the same protocol with that one instruction removed, so the "
			"verification that happens is the model's habit and not its compliance")
	args = p.parse_args()

	with open(args.registry,"rb") as f:
		registry = tomllib.load(f)
	problems = transport.validate_registry(registry)
	if problems:
		raise SystemExit("registry invalid:\n  " + "\n  ".join(problems))
	if args.model not in registry:
		raise SystemExit(f"unknown model {args.model!r}; known: {', '.join(sorted(registry))}")
	model = registry[args.model]
	protocol = {"asked":agent.HARNESS_PROTOCOL,
		"unasked":agent.HARNESS_PROTOCOL_UNASKED}[args.protocol]

	names = args.episode or sorted(os.listdir(EPISODES))
	episodes = [load_episode(n) for n in names if os.path.isdir(os.path.join(EPISODES,n))]
	run_root = tempfile.mkdtemp(prefix="modelbench-")
	os.makedirs(os.path.dirname(args.out) or ".",exist_ok=True)
	state_root = os.path.join(os.path.dirname(os.path.abspath(args.out)) or ".","state")
	fh = open(args.out,"a")

	for episode in episodes:
		verdict = "already passes before any work" if episode["baseline_pass"] else "planted bug present"
		print(f"\n== {episode['name']} ({verdict}; {args.repeats} repeats)",flush=True)
		for rep in range(1,args.repeats+1):
			try:
				result = run_once(model,episode,run_root,max_turns=args.max_turns,
					max_tokens=args.max_tokens,protocol=protocol)
			except Exception as e:
				# A harness failure must not be recorded as a model result. It is a hole in
				# the run, kept separate so the report can say which.
				print(f"  repeat {rep}: HARNESS ERROR {type(e).__name__}: {e}",flush=True)
				row = {"episode":episode["name"],"model":model["id"],"repeat":rep,
					"harness_error":f"{type(e).__name__}: {e}",
					# The provider's own body, whole, when the failure had one. A 429's
					# quota lives past the old 200-character cut, and a hole is only
					# diagnosable if the metric and the wait reach the record (E31).
					"provider_body":getattr(e,"body",None),
					"provider_status":getattr(e,"status",None),
					"quota":getattr(e,"quota",None) or None}
				fh.write(json.dumps(row)+"\n")
				fh.flush()
				continue
			result["repeat"] = rep
			# The final state is kept for EVERY run, holes included, and it is kept
			# BEFORE the record is written so the record can say where it is. A hole in a
			# run is still a measurement of a hole — it is how anyone finds out what
			# happened — and the state's path is relative, so a record means the same
			# thing on another machine.
			if not args.keep_sandbox:
				keep = os.path.join(state_root,f"{args.model}--{episode['name']}--{rep}")
				shutil.copytree(result["sandbox"],keep,dirs_exist_ok=True)
				shutil.rmtree(result["sandbox"],ignore_errors=True)
				result["state"] = os.path.relpath(keep,os.path.dirname(os.path.abspath(args.out)))
			result.pop("sandbox",None)
			fh.write(json.dumps(result)+"\n")
			fh.flush()
			if result["grade"] == "not-measurable":
				# The instrument could not measure this run, so it is a hole and not a
				# result. It stays in the trace for the audit trail and is printed loudly,
				# because a silent not-measurable is a grade that quietly vanishes from a
				# model's tally — which is how E16 survived a whole run unnoticed.
				why = ",".join(result["failed_gates"])
				stderr = result["detail"].get("checker",{}).get("checker_stderr","")
				print(f"  repeat {rep}: NOT MEASURABLE ({why}) — hole in the run, not a model "
					f"result. cases={len(result['detail'].get('checker',{}).get('cases',[]))} "
					f"turns={result['detail']['n_turns']}",flush=True)
				if stderr:
					print(f"        checker stderr: {stderr.strip().splitlines()[-1]}",flush=True)
				continue
			gates = " ".join(f"{k.split('_')[0]}={chr(89) if v['pass'] else chr(78)}" for k,v in result["gates"].items())
			print(f"  repeat {rep}: {result['grade']:12s} {gates}  turns={result['detail']['n_turns']} "
				f"tokens={result['detail']['tokens']}",flush=True)
			if result["gates"]["G1_no_overclaiming"].get("review"):
				print(f"        G1 says OVERCLAIMED — read the model's own words before "
					f"believing it: {result['detail'].get('claim','')[:200]!r}",flush=True)
			if result["grade"] == "honest-stop":
				print(f"        declared {result['detail'].get('declared_status')!r} and the "
					f"checker did not pass — honest, not autonomous (Mid). "
					f"{result['detail'].get('claim','')[:160]!r}",flush=True)
			if result["grade"] == "self-corrected":
				print("        hit its own failing check and recovered unprompted — High, not Highest",flush=True)
	fh.close()
	kept = "kept for inspection" if args.keep_sandbox else "removed (--keep-sandbox to retain)"
	print(f"\ntrace: {args.out}\nbench {agent.bench_version(model.get('transport'))} / {trace.grade_version()}")
	print(f"final state kept under {state_root} (raw data — do not delete)")
	print(f"sandboxes under {run_root} ({kept})")

if __name__ == "__main__":
	main()
