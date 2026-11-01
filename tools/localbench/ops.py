#!/usr/bin/env python3
"""localbench ops: speed, memory and concurrency for local models.

These are operating measurements, not capability scores. They exist to answer the
acceptance question (several models resident without stress) and to give each model's
page a speed and memory figure.

    ops.py --models m1,m2 --out DIR [--xprompt PATH] [--host H] [--threads 4] [--ctx 8192]
    ops.py --concurrency m1,m2,m3 --out DIR [same options] [--model-option MODEL:KEY=VALUE]
    ops.py --stress m1,m2,m3 --out DIR [same options] [--stress-minutes 10]

--model-option applies to one model only and wins over the shared options, e.g.
--model-option gemma4:e4b:num_gpu=0 pins the model off the card. The effective option
set is recorded per model in the output JSON.
"""
import argparse,json,os,shutil,statistics,subprocess,sys,threading,time,urllib.request
from concurrent.futures import ThreadPoolExecutor

WORDS = ("alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike "
	"november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu").split()
LENGTHS = (100, 1000, 4000)
REPS = 3
COUNT_PROMPT = "List the integers from 1 to 40, separated by commas. Output only the numbers."

def human_filler(target_tokens, tag=None):
	"""Approximate English filler, ~4 characters per token, with the task at the end.

	A tag makes the prompt textually unique at its start, so a repeat cannot reuse
	Ollama's prompt-prefix KV cache and prefill is actually measured.
	"""
	target_chars = max(200, target_tokens * 4)
	parts, n = [], 0
	if tag is not None:
		parts.append(f"Request {tag}.")
	while sum(len(p) + 1 for p in parts) < target_chars:
		n += 1
		parts.append(f"Paragraph {n}: " + " ".join(WORDS[(n + i) % len(WORDS)] for i in range(30)))
	return "\n".join(parts) + "\n\n" + COUNT_PROMPT

def median(values):
	vals = [v for v in values if isinstance(v, (int, float))]
	return round(statistics.median(vals), 3) if vals else None

def resolve_xprompt(arg):
	if arg:
		return arg
	if os.environ.get("XPROMPT"):
		return os.environ["XPROMPT"]
	found = shutil.which("xprompt")
	if found:
		return found
	fail("xprompt not found; pass --xprompt")

def fail(msg, code=2):
	sys.stderr.write(f"ops: {msg}\n")
	sys.exit(code)

def host_parts(host):
	if not host:
		host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
	host = host.strip()
	if "://" not in host:
		host = "http://" + host
	from urllib.parse import urlparse
	p = urlparse(host)
	return p.hostname or "localhost", p.port or 11434

def api_ps(host):
	h, p = host_parts(host)
	try:
		with urllib.request.urlopen(f"http://{h}:{p}/api/ps", timeout=10) as r:
			return json.loads(r.read())
	except Exception:
		return {"models": []}

def ps_lookup(ps, model):
	"""Exact tag match, tolerating a `:latest` suffix on either side.

	Matching the family alone (`gemma4:e4b` against `gemma4:12b`) silently returns the
	wrong entry when two tags of one family are resident, which the stress summary would
	then report as memory.
	"""
	for m in ps.get("models", []):
		name = m.get("name") or m.get("model") or ""
		if name.removesuffix(":latest") == model.removesuffix(":latest"):
			return {"size": m.get("size"), "size_vram": m.get("size_vram")}
	return None

def ps_entry(host, model):
	return ps_lookup(api_ps(host), model)

def call(xprompt, model, prompt, host, threads, ctx, num_predict=64, max_turns=1, extra=None):
	base = ["temperature=0", "seed=42", f"num_ctx={ctx}", f"num_thread={threads}", f"num_predict={num_predict}"]
	cmd = [xprompt, model, "--json", "--no-think", "--max-turns", str(max_turns), "--prompt", prompt]
	for opt in base + list(extra or []):
		cmd += ["--option", opt]
	if host:
		cmd += ["--host", host]
	t0 = time.time()
	proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
	wall = time.time() - t0
	try:
		data = json.loads(proc.stdout)
	except (json.JSONDecodeError, ValueError):
		data = {"content": "", "error": (proc.stdout + proc.stderr)[:300]}
	timings = data.get("timings") or [{}]
	t = timings[0] if timings else {}
	return {"wall_s": round(wall, 3), "exit": proc.returncode,
		"prompt_tokens": t.get("prompt_eval_count") or 0,
		"eval_tokens": t.get("eval_count") or 0,
		"prefill_s": round((t.get("prompt_eval_duration_ns") or 0) / 1e9, 4),
		"gen_s": round((t.get("eval_duration_ns") or 0) / 1e9, 4),
		"error": data.get("error")}

def speed_for_model(xprompt, model, out_dir, host, threads, ctx, extra=None):
	result = {"model": model, "options": list(extra or []), "lengths": {}, "memory": None}
	call(xprompt, model, "Reply with exactly: OK", host, threads, min(ctx, 2048), num_predict=8, extra=extra)
	result["memory"] = ps_entry(host, model)
	for target in LENGTHS:
		# a unique start per repeat defeats the prompt-prefix cache; otherwise
		# repeats 2..n report a near-zero prefill and the median is not a measurement
		runs = [call(xprompt, model, human_filler(target, tag=f"{target}-{i}"), host, threads, ctx, extra=extra) for i in range(REPS)]
		result["lengths"][str(target)] = {
			"prompt_tokens": median([r["prompt_tokens"] for r in runs]),
			"prefill_s": median([r["prefill_s"] for r in runs]),
			"gen_s": median([r["gen_s"] for r in runs]),
			"prefill_tok_s": median([r["prompt_tokens"] / r["prefill_s"] for r in runs if r["prefill_s"]]),
			"gen_tok_s": median([r["eval_tokens"] / r["gen_s"] for r in runs if r["gen_s"]]),
			"wall_s": median([r["wall_s"] for r in runs]),
		}
	out = os.path.join(out_dir, model.replace(":", "_") + ".json")
	with open(out, "w", encoding="utf-8") as f:
		json.dump(result, f, indent=1, sort_keys=True)
	return result

def count_prompt(tag):
	# a unique tag defeats the prompt-prefix cache, and the 1-40 list makes generation real;
	# a two-token "OK" answer measured cache hits rather than concurrency
	return f"Request {tag}.\n{COUNT_PROMPT}"

def concurrency(xprompt, models, out_dir, host, threads, ctx, rounds=3, model_options=None):
	model_options = model_options or {}
	def one(model, tag):
		return call(xprompt, model, count_prompt(tag), host, threads, min(ctx, 2048), num_predict=64, extra=model_options.get(model))
	timing = {}
	for m in models:
		one(m, f"warm-{m}")
		solo = one(m, f"solo-{m}")
		timing[m] = {"solo_s": solo["wall_s"], "options": list(model_options.get(m) or []), "error": solo.get("error")}
	concurrent = []
	for r in range(rounds):
		with ThreadPoolExecutor(max_workers=len(models)) as ex:
			futs = [ex.submit(one, m, f"round{r}-{m}") for m in models]
			rows = [f.result() for f in futs]
		concurrent.append({"round": r + 1, "walls": {m: row["wall_s"] for m, row in zip(models, rows)},
			"errors": {m: row.get("error") for m, row in zip(models, rows)},
			"eval_tokens": {m: row.get("eval_tokens") for m, row in zip(models, rows)},
			"loadavg": list(os.getloadavg())})
	result = {"models": models, "options": {m: list(model_options.get(m) or []) for m in models},
		"solo": timing, "concurrent": concurrent, "ps_after": api_ps(host), "rounds": rounds}
	failed = [m for m, v in timing.items() if v.get("error")]
	if failed:
		sys.stderr.write("ops: WARNING solo call failed for " + ", ".join(failed) + "\n")
	with open(os.path.join(out_dir, "concurrency.json"), "w", encoding="utf-8") as f:
		json.dump(result, f, indent=1, sort_keys=True)
	return result

STRESS_PLAN = ((100, 64), (500, 96), (1000, 64))

def proc_sample():
	"""Load, memory and the counters that only move under real pressure."""
	sample = {"ts": round(time.time(), 3), "loadavg": list(os.getloadavg())}
	with open("/proc/vmstat") as f:
		for line in f:
			name, _, value = line.partition(" ")
			if name in ("pswpin", "pswpout", "oom_kill"):
				sample[name] = int(value)
	with open("/proc/meminfo") as f:
		for line in f:
			name, _, value = line.partition(":")
			if name in ("MemAvailable", "SwapFree"):
				sample[name] = int(value.split()[0])
	return sample

def stress_drift(calls):
	"""Per-target drift, so a rotating prompt mix cannot fake a trend.

	Comparing the first and last third of all calls confounds elapsed time with target
	length, because the rotation gives each third a different mix: 12 rounds of a 3-cycle
	make the first third [100, 500, 1000, 100] and the last [1000, 100, 500, 1000].
	"""
	drifts, by_target = [], {}
	for target in sorted({c["target"] for c in calls}):
		walls = [c["wall_s"] for c in calls if c["target"] == target]
		half = max(1, len(walls) // 2)
		first, last = median(walls[:half]), median(walls[-half:])
		by_target[str(target)] = {"calls": len(walls), "wall_median_s": median(walls),
			"drift_x": round(last / first, 2) if first else None}
		if first:
			drifts.append(last / first)
	return by_target, round(median(drifts), 2) if drifts else None

def stress(xprompt, models, out_dir, host, threads, ctx, minutes=10, model_options=None):
	"""Sustained mixed calls on a resident set, for the acceptance question.

	The concurrency arm proves three short calls overlap; this asks whether they keep
	overlapping under load, so latency drift, swap and OOM are the evidence. Rounds are
	the unit, so the run may overrun the clock by one round of the slowest model.
	"""
	model_options = model_options or {}
	for m in models:
		call(xprompt, m, count_prompt(f"warm-{m}"), host, threads, min(ctx, 2048), num_predict=32, extra=model_options.get(m))
	before = proc_sample()
	ps_before = api_ps(host)
	deadline = time.time() + minutes * 60
	calls, samples, round_no = [], [], 0
	while time.time() < deadline:
		round_no += 1
		plan = [(m, *STRESS_PLAN[(round_no + i) % len(STRESS_PLAN)]) for i, m in enumerate(models)]
		with ThreadPoolExecutor(max_workers=len(models)) as ex:
			futs = [ex.submit(call, xprompt, m, human_filler(target, tag=f"stress-{round_no}-{m}"), host, threads,
				min(ctx, max(2048, target * 2)), num_predict=num_predict, extra=model_options.get(m))
				for m, target, num_predict in plan]
			rows = [f.result() for f in futs]
		for (m, target, _), row in zip(plan, rows):
			calls.append({"round": round_no, "model": m, "target": target, **row})
		samples.append(proc_sample())
	after = proc_sample()
	ps_after = api_ps(host)
	summary = {}
	for m in models:
		mcalls = [c for c in calls if c["model"] == m]
		by_target, drift = stress_drift(mcalls)
		entry = ps_lookup(ps_after, m) or {}
		summary[m] = {"calls": len(mcalls),
			"failures": sum(1 for c in mcalls if c.get("error") or c.get("exit") != 0),
			"wall_median_s": median([c["wall_s"] for c in mcalls]),
			"by_target": by_target, "drift_x": drift,
			"size_vram_mb": round((entry.get("size_vram") or 0) / 2**20) if entry else None,
			"size_ram_mb": round((entry.get("size") or 0) / 2**20) if entry else None}
	result = {"models": models, "minutes": minutes, "rounds": round_no,
		"options": {m: list(model_options.get(m) or []) for m in models},
		"before": before, "after": after, "ps_before": ps_before, "ps_after": ps_after,
		"summary": summary, "calls": calls, "samples": samples}
	with open(os.path.join(out_dir, "stress.json"), "w", encoding="utf-8") as f:
		json.dump(result, f, indent=1, sort_keys=True)
	return result

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--models", default=None)
	ap.add_argument("--concurrency", default=None)
	ap.add_argument("--stress", default=None)
	ap.add_argument("--stress-minutes", type=int, default=10)
	ap.add_argument("--out", required=True)
	ap.add_argument("--xprompt", default=None)
	ap.add_argument("--host", default=None)
	ap.add_argument("--threads", type=int, default=4)
	ap.add_argument("--ctx", type=int, default=8192)
	ap.add_argument("--model-option", action="append", default=[], metavar="MODEL:KEY=VALUE")
	args = ap.parse_args()
	if not args.models and not args.concurrency and not args.stress:
		fail("pass --models, --concurrency and/or --stress")
	xprompt = resolve_xprompt(args.xprompt)
	os.makedirs(args.out, exist_ok=True)
	model_options = {}
	for item in args.model_option:
		model, sep, opt = item.rpartition(":")
		if not sep or "=" not in opt:
			fail(f"bad --model-option {item!r}; expected MODEL:KEY=VALUE")
		model_options.setdefault(model, []).append(opt)
	if args.models:
		for m in [x.strip() for x in args.models.split(",") if x.strip()]:
			r = speed_for_model(xprompt, m, args.out, args.host, args.threads, args.ctx, extra=model_options.get(m))
			print(f"{m}: " + " | ".join(f"{k} tok/s prefill={v['prefill_tok_s']} gen={v['gen_tok_s']}" for k, v in r["lengths"].items()))
	if args.concurrency:
		models = [x.strip() for x in args.concurrency.split(",") if x.strip()]
		r = concurrency(xprompt, models, args.out, args.host, args.threads, args.ctx, model_options=model_options)
		print(json.dumps(r["concurrent"], indent=1))
	if args.stress:
		models = [x.strip() for x in args.stress.split(",") if x.strip()]
		r = stress(xprompt, models, args.out, args.host, args.threads, args.ctx, args.stress_minutes, model_options=model_options)
		print(json.dumps(r["summary"], indent=1))

if __name__ == "__main__":
	main()
