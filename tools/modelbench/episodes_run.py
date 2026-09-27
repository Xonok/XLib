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
			gates = " ".join(f"{k.split('_')[0]}={'Y' if v['pass'] else 'N'}" for k,v in result["gates"].items())
			print(f"  repeat {rep}: {result['grade']:12s} {gates}  turns={result['detail']['n_turns']} "
				f"tokens={result['detail']['tokens']}",flush=True)
			if not args.keep_sandbox:
				shutil.rmtree(result["sandbox"],ignore_errors=True)
	fh.close()
	kept = "kept for inspection" if args.keep_sandbox else "removed (--keep-sandbox to retain)"
	print(f"\ntrace: {args.out}\nsandboxes under {run_root} ({kept})")

if __name__ == "__main__":
	main()
