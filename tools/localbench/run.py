import argparse,hashlib,json,os,re,shutil,statistics,subprocess,sys,tempfile,time,uuid
from datetime import datetime,timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS_DEFAULT = ROOT / "tasks"

TOOL_FLAGS = {"read": "--read", "grep": "--grep", "ls": "--ls", "bash": "--bash", "write": "--write"}

def resolve_xprompt(arg):
	if arg:
		return arg
	env = os.environ.get("XPROMPT")
	if env:
		return env
	xlib = os.environ.get("XLIB")
	if xlib:
		cand = Path(xlib) / "tools" / "xprompt"
		if cand.exists():
			return str(cand)
	w = shutil.which("xprompt")
	if w:
		return w
	return "xprompt"

def bench_version(tasks_dir, run_py):
	files = []
	run_py = Path(run_py)
	if run_py.exists():
		files.append((str(run_py.relative_to(run_py.parent)), run_py))
	tasks_dir = Path(tasks_dir)
	if tasks_dir.exists():
		for p in tasks_dir.rglob("*"):
			if p.is_file():
				rel = p.relative_to(tasks_dir.parent).as_posix() if False else None
				# relative to localbench root (parent of tasks)
				rel = p.relative_to(run_py.parent).as_posix()
				files.append((rel, p))
	# dedupe by path
	seen = set()
	uniq = []
	for rel, p in files:
		if rel in seen:
			continue
		seen.add(rel)
		uniq.append((rel, p))
	uniq.sort(key=lambda x: x[0])
	import hashlib
	h = hashlib.sha256()
	for rel, p in uniq:
		fh = hashlib.sha256()
		fh.update(p.read_bytes())
		h.update((rel + "\0" + fh.hexdigest() + "\0").encode())
	return "sha256:" + h.hexdigest()

def median(vals):
	v = [x for x in vals if x is not None]
	if not v:
		return None
	return statistics.median(v)

def iso_now():
	return datetime.now(timezone.utc).isoformat()

def load_tasks(tasks_dir, family_filter, case_filter):
	out = []
	tasks_dir = Path(tasks_dir)
	for fam_dir in sorted(tasks_dir.iterdir()):
		if not fam_dir.is_dir():
			continue
		if family_filter and fam_dir.name != family_filter:
			continue
		for case_dir in sorted(fam_dir.iterdir()):
			if not case_dir.is_dir() or not (case_dir / "task.json").exists():
				continue
			if case_filter and case_dir.name != case_filter:
				continue
			task = json.loads((case_dir / "task.json").read_text())
			out.append((fam_dir.name, case_dir.name, case_dir, task))
	return out

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--model", required=True)
	ap.add_argument("--out", required=True)
	ap.add_argument("--tasks", default=None)
	ap.add_argument("--task", default=None)
	ap.add_argument("--case", default=None)
	ap.add_argument("--repeats", type=int, default=1)
	ap.add_argument("--xprompt", default=None)
	ap.add_argument("--host", default=None)
	ap.add_argument("--workdir", default=None)
	ap.add_argument("--keep", action="store_true")
	ap.add_argument("--no-warmup", action="store_true")
	ap.add_argument("--think", action="store_true", help="enable model thinking (default off)")
	ap.add_argument("--no-final", action="store_true")
	ap.add_argument("--option", action="append", default=[])
	args = ap.parse_args()

	out_dir = Path(args.out)
	out_dir.mkdir(parents=True, exist_ok=True)
	tasks_dir = Path(args.tasks) if args.tasks else TASKS_DEFAULT
	xprompt = resolve_xprompt(args.xprompt)
	bv = bench_version(tasks_dir, ROOT / "run.py")
	xprompt_sha = None
	try:
		xprompt_sha = __import__("hashlib").sha256(Path(xprompt).read_bytes()).hexdigest()
	except Exception:
		xprompt_sha = None

	workdir = Path(args.workdir) if args.workdir else (out_dir / "work")
	workdir.mkdir(parents=True, exist_ok=True)

	# warmup — same host/options/think as the runs, or the first scored call pays a reload
	if not args.no_warmup:
		cmd = [xprompt, args.model, "--json", "--max-turns", "1", "Reply with exactly: OK"]
		for o in args.option:
			if "=" in o:
				cmd += ["--option", o]
		cmd.append("--think" if args.think else "--no-think")
		if args.host:
			cmd += ["--host", args.host]
		try:
			proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True, timeout=300)
			raw = proc.stdout
		except subprocess.TimeoutExpired as e:
			raw = e.stdout or ""
			if isinstance(raw, bytes):
				raw = raw.decode("utf-8", "replace")
		try:
			warmup_obj = json.loads(raw)
		except (json.JSONDecodeError, ValueError):
			warmup_obj = {"raw_stdout": raw}
		(out_dir / "warmup.json").write_text(json.dumps(warmup_obj, indent=2, sort_keys=True))

	runner_opts = {}
	for o in args.option:
		if "=" in o:
			k, v = o.split("=", 1)
			runner_opts[k] = v

	tasks = load_tasks(tasks_dir, args.task, args.case)

	# accumulate per-case summary
	case_runs = {}

	for fam, case, case_dir, task in tasks:
		task_tools = task.get("tools", [])
		max_turns = int(task.get("max_turns", 1))
		timeout_s = int(task.get("timeout_s", 120))
		task_opts = task.get("options", {}) or {}
		prompt_text = task.get("prompt")
		prompt_path = None
		if task.get("prompt_file"):
			# passed by path: a large fixture would exceed MAX_ARG_STRLEN as argv text
			prompt_path = (case_dir / task["prompt_file"]).resolve()
		verify_command = task.get("verify_command")
		fixture = case_dir / "fixture"

		run_metrics = []
		for rep in range(1, args.repeats + 1):
			runid = f"{fam}-{case}-r{rep}-{uuid.uuid4().hex[:8]}"
			sandbox = workdir / runid
			sandbox.mkdir(parents=True, exist_ok=True)
			if fixture.exists():
				shutil.copytree(fixture, sandbox, dirs_exist_ok=True)
			run_dir = out_dir / runid
			run_dir.mkdir(parents=True, exist_ok=True)

			# merged options: defaults -> runner -> task (task wins), all str
			merged = {"temperature": "0", "seed": "42"}
			for k, v in runner_opts.items():
				merged[k] = str(v)
			for k, v in task_opts.items():
				merged[k] = str(v)

			started = iso_now()
			start_wall = time.time()
			prompt_args = ["--prompt-file", str(prompt_path)] if prompt_path is not None else ["--prompt", prompt_text]
			cmd = [xprompt, args.model, "--json"] + prompt_args + ["--max-turns", str(max_turns), "--timeout", str(timeout_s)]
			for t in task_tools:
				if t in TOOL_FLAGS:
					cmd.append(TOOL_FLAGS[t])
			cmd.append("--think" if task.get("think", args.think) else "--no-think")
			for k, v in merged.items():
				cmd += ["--option", f"{k}={v}"]
			if args.host:
				cmd += ["--host", args.host]

			timed_out = False
			returncode = None
			stdout = ""
			stderr = ""
			try:
				proc = subprocess.run(cmd, cwd=str(sandbox), capture_output=True, text=True, timeout=timeout_s + 30)
				returncode = proc.returncode
				stdout = proc.stdout or ""
				stderr = proc.stderr or ""
			except subprocess.TimeoutExpired as e:
				timed_out = True
				stdout = e.stdout or ""
				stderr = e.stderr or ""
				if isinstance(stdout, bytes):
					stdout = stdout.decode("utf-8", "replace")
				if isinstance(stderr, bytes):
					stderr = stderr.decode("utf-8", "replace")
				returncode = None

			(run_dir / "stdout.txt").write_text(stdout)
			(run_dir / "stderr.txt").write_text(stderr)

			# parse json
			data = None
			xprompt_error = None
			if stdout.strip():
				try:
					data = json.loads(stdout)
				except (json.JSONDecodeError, ValueError):
					xprompt_error = "stdout was not JSON"
			if isinstance(data, dict):
				if data.get("error") is not None:
					xprompt_error = data.get("error")
			if not isinstance(data, dict):
				data = {}

			turns = data.get("turns", 0)
			if not isinstance(turns, int):
				try:
					turns = int(turns)
				except (TypeError, ValueError):
					turns = 0
			tool_calls = data.get("tool_calls", [])
			if not isinstance(tool_calls, list):
				tool_calls = []
			timings = data.get("timings", [])
			if not isinstance(timings, list):
				timings = []

			prompt_tokens = sum((t.get("prompt_eval_count") or 0) for t in timings if isinstance(t, dict))
			eval_tokens = sum((t.get("eval_count") or 0) for t in timings if isinstance(t, dict))
			prefill_s = sum(((t.get("prompt_eval_duration_ns") or 0) / 1e9) for t in timings if isinstance(t, dict))
			gen_s = sum(((t.get("eval_duration_ns") or 0) / 1e9) for t in timings if isinstance(t, dict))
			prefill_tok_s = (prompt_tokens / prefill_s) if prefill_s > 0 else None
			gen_tok_s = (eval_tokens / gen_s) if gen_s > 0 else None
			wall_time_s = data.get("wall_time_s")
			if not isinstance(wall_time_s, (int, float)):
				wall_time_s = time.time() - start_wall

			# checker
			check_path = case_dir / "check.py"
			checker_error = False
			checker = {"ok": False, "contract_clean": False, "reason": "checker not run", "detail": {}}
			try:
				cp = subprocess.run([sys.executable, str(check_path)], cwd=str(sandbox), env={**os.environ, "LB_STDOUT": str(run_dir / "stdout.txt"), "LB_TASK_DIR": str(case_dir), "LB_META": str(run_dir / "meta.json")}, capture_output=True, text=True, timeout=120)
				if cp.returncode == 2:
					checker_error = True
				if cp.stdout.strip():
					try:
						parsed = json.loads(cp.stdout.strip().splitlines()[-1])
						if not isinstance(parsed, dict):
							raise ValueError("bad")
						checker = {
							"ok": bool(parsed.get("ok")),
							"contract_clean": bool(parsed.get("contract_clean")),
							"reason": str(parsed.get("reason", "")),
							"detail": parsed.get("detail", {}),
						}
					except (json.JSONDecodeError, ValueError):
						checker_error = True
				else:
					checker_error = True
			except subprocess.TimeoutExpired:
				checker_error = True
			except Exception:
				checker_error = True

			# verified
			verified = None
			if verify_command is not None:
				verified = False
				if tool_calls:
					write_idx = [i for i, tc in enumerate(tool_calls) if isinstance(tc, dict) and tc.get("name") == "write"]
					threshold = max(write_idx) if write_idx else 0
					pat = re.compile(verify_command)
					for i, tc in enumerate(tool_calls):
						if isinstance(tc, dict) and tc.get("name") == "bash" and i > threshold:
							cmdstr = tc.get("arguments", {}).get("command", "") if isinstance(tc.get("arguments"), dict) else ""
							if pat.search(str(cmdstr)):
								verified = True
								break

			# final copy
			final_state_kept = False
			if not args.no_final:
				final_dir = run_dir / "final"
				if final_dir.exists():
					shutil.rmtree(final_dir)
				if sandbox.exists():
					shutil.copytree(sandbox, final_dir, dirs_exist_ok=True)
				final_state_kept = True
			if not args.keep:
				shutil.rmtree(sandbox, ignore_errors=True)

			meta = {
				"kind": "task",
				"model": args.model,
				"task": fam,
				"case": case,
				"repeat": rep,
				"started": started,
				"bench_version": bv,
				"xprompt_sha256": xprompt_sha,
				"options": merged,
				"tools": task_tools,
				"max_turns": max_turns,
				"think": bool(task.get("think", args.think)),
				"exit_code": returncode,
				"timed_out": timed_out,
				"wall_time_s": wall_time_s,
				"turns": turns,
				"tool_calls": tool_calls,
				"prompt_tokens": prompt_tokens,
				"eval_tokens": eval_tokens,
				"prefill_s": prefill_s,
				"gen_s": gen_s,
				"prefill_tok_s": prefill_tok_s,
				"gen_tok_s": gen_tok_s,
				"checker": checker,
				"checker_error": checker_error,
				"verified": verified,
				"final_state_kept": final_state_kept,
				"xprompt_error": xprompt_error,
			}
			(run_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))

			run_metrics.append({
				"pass": bool(checker.get("ok")) if not checker_error else False,
				"contract": bool(checker.get("contract_clean")) if not checker_error else False,
				"wall": wall_time_s,
				"prefill": prefill_tok_s,
				"gen": gen_tok_s,
			})

		# summary per case
		n = len(run_metrics)
		passes = sum(1 for m in run_metrics if m["pass"])
		contracts = sum(1 for m in run_metrics if m["contract"])
		med_wall = median([m["wall"] for m in run_metrics])
		med_prefill = median([m["prefill"] for m in run_metrics])
		med_gen = median([m["gen"] for m in run_metrics])
		print(f"{args.model} {fam} {case} n={n} pass={passes} contract={contracts} median_wall={med_wall} median_prefill_tok_s={med_prefill} median_gen_tok_s={med_gen}")

if __name__ == "__main__":
	main()
