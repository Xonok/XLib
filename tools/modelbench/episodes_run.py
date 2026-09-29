"""Episode runner: sets up a sandbox, drives one model through it, scores the trace.

An episode gets a fresh copy of its directory every time, so a repeat run cannot inherit
the previous run's fix. That is the whole point of repeating: whether a model finds the
bug on its own second and third attempts is part of what trust means.
"""

import argparse,agent,json,os,shutil,subprocess,sys,tempfile,time,tomllib,trace,transport

HERE = os.path.dirname(os.path.abspath(__file__))
EPISODES = os.path.join(HERE,"episodes")
REGISTRY = os.path.join(HERE,"models.toml")

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

def run_once(model,episode,run_root,max_turns=agent.MAX_TURNS,max_tokens=4096):
	"""One episode attempt in a throwaway copy of the episode directory."""
	sandbox = tempfile.mkdtemp(prefix=f"ep-{episode['name']}-",dir=run_root)
	shutil.copytree(episode["dir"],sandbox,dirs_exist_ok=True)
	# REQUEST.md is the harness's, not the model's — it is what the agent loop renders into
	# the first user turn. check.py stays visible on purpose: the model is told to confirm
	# with it, so hiding it would be a lie, and it holds no secret (every expected value is
	# already in SPEC.md's reconciliation table). Error (f) — the right information in
	# context, unaccounted for — is only measurable if the information really is there.
	if model.get("transport") == "harness":
		raw = agent.run_episode_harness(model,episode["request"],sandbox,
			max_turns=max_turns,max_tokens=max_tokens)
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
		# was measured on. Two versions because the two sides are allowed to move at
		# different rates: bench_* changes invalidate, grade_* changes are re-derivable.
		"bench_version":agent.bench_version(),"grade_version":trace.grade_version(),
		# The raw turns are KEPT. analyse() reads them, so a new gate used to cost a
		# re-measurement — which is how six criterion changes in one day turned into
		# discarded runs. With them in the record, evaluation can be re-derived offline and
		# measurement stops being repeated for the sake of a scoring change.
		"trace":{"turns":raw.get("turns",[]),"finished":raw.get("finished"),
			"claim":raw.get("claim"),"status":raw.get("status"),
			"n_turns":raw.get("n_turns"),"usage":raw.get("usage")},
		# The confounds of the harness path travel with the result, so a report cannot
		# quote a harness grade beside a direct grade without the difference showing.
		"provenance":{"transport":raw.get("transport","four-tool"),
			"timed_out":raw.get("timed_out"),"turn_budget":raw.get("turn_budget"),
			"over_budget":raw.get("over_budget")},
		**result}

def main():
	p = argparse.ArgumentParser(description="Run agentic benchmark episodes")
	p.add_argument("--model",required=True)
	p.add_argument("--episode",action="append",help="repeatable; default = all")
	p.add_argument("--repeats",type=int,default=3)
	p.add_argument("--max-turns",type=int,default=agent.MAX_TURNS)
	# Reasoning-heavy models spend thousands of tokens thinking before answering and
	# return EMPTY content when truncated (finish_reason=length). In a 12-turn episode
	# that is a budget problem masquerading as a model that cannot follow instructions.
	p.add_argument("--max-tokens",type=int,default=4096)
	p.add_argument("--out",required=True)
	p.add_argument("--registry",default=REGISTRY)
	p.add_argument("--keep-sandbox",action="store_true")
	args = p.parse_args()

	with open(args.registry,"rb") as f:
		registry = tomllib.load(f)
	problems = transport.validate_registry(registry)
	if problems:
		raise SystemExit("registry invalid:\n  " + "\n  ".join(problems))
	if args.model not in registry:
		raise SystemExit(f"unknown model {args.model!r}; known: {', '.join(sorted(registry))}")
	model = registry[args.model]

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
				result = run_once(model,episode,run_root,max_turns=args.max_turns,max_tokens=args.max_tokens)
			except Exception as e:
				# A harness failure must not be recorded as a model result. It is a hole in
				# the run, kept separate so the report can say which.
				print(f"  repeat {rep}: HARNESS ERROR {type(e).__name__}: {e}",flush=True)
				fh.write(json.dumps({"episode":episode["name"],"model":model["id"],
					"repeat":rep,"harness_error":f"{type(e).__name__}: {e}"})+"\n")
				fh.flush()
				continue
			result["repeat"] = rep
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
			if not args.keep_sandbox:
				# The final on-disk state is raw data, kept by default beside the trace it came
				# from. Deleting it is what made the E18 diagnosis impossible on the 2026-09-27
				# runs, and the 2026-09-28 runs had to be rescued from /tmp by accident. The
				# human's point: "failure to account for data that you already have simply
				# because you can't use it effectively anymore."
				keep = os.path.join(state_root,f"{args.model}--{episode['name']}--{rep}")
				shutil.copytree(result["sandbox"],keep,dirs_exist_ok=True)
				shutil.rmtree(result["sandbox"],ignore_errors=True)
	fh.close()
	kept = "kept for inspection" if args.keep_sandbox else "removed (--keep-sandbox to retain)"
	print(f"\ntrace: {args.out}\nbench {agent.bench_version()} / {trace.grade_version()}")
	print(f"final state kept under {state_root} (raw data — do not delete)")
	print(f"sandboxes under {run_root} ({kept})")

if __name__ == "__main__":
	main()
