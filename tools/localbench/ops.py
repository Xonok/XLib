#!/usr/bin/env python3
"""localbench ops: speed, memory and concurrency for local models.

These are operating measurements, not capability scores. They exist to answer the
acceptance question (several models resident without stress) and to give each model's
page a speed and memory figure.

    ops.py --models m1,m2 --out DIR [--xprompt PATH] [--host H] [--threads 4] [--ctx 8192]
    ops.py --concurrency m1,m2,m3 --out DIR [same options]
"""
import argparse,json,os,shutil,statistics,subprocess,sys,threading,time,urllib.request
from concurrent.futures import ThreadPoolExecutor

WORDS = ("alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike "
	"november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu").split()
LENGTHS = (100, 1000, 4000)
REPS = 3
COUNT_PROMPT = "List the integers from 1 to 40, separated by commas. Output only the numbers."

def human_filler(target_tokens):
	"""Approximate English filler, ~4 characters per token, with the task at the end."""
	target_chars = max(200, target_tokens * 4)
	parts, n = [], 0
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

def ps_entry(host, model):
	for m in api_ps(host).get("models", []):
		if m.get("name", "").split(":")[0] == model.split(":")[0] or m.get("name") == model or m.get("model") == model:
			return {"size": m.get("size"), "size_vram": m.get("size_vram")}
	return None

def call(xprompt, model, prompt, host, threads, ctx, num_predict=64, max_turns=1):
	cmd = [xprompt, model, "--json", "--no-think", "--max-turns", str(max_turns), "--prompt", prompt,
		"--option", "temperature=0", "--option", "seed=42",
		"--option", f"num_ctx={ctx}", "--option", f"num_thread={threads}", "--option", f"num_predict={num_predict}"]
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

def speed_for_model(xprompt, model, out_dir, host, threads, ctx):
	result = {"model": model, "lengths": {}, "memory": None}
	call(xprompt, model, "Reply with exactly: OK", host, threads, min(ctx, 2048), num_predict=8)
	result["memory"] = ps_entry(host, model)
	for target in LENGTHS:
		prompt = human_filler(target)
		runs = [call(xprompt, model, prompt, host, threads, ctx) for _ in range(REPS)]
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

def concurrency(xprompt, models, out_dir, host, threads, ctx, rounds=3):
	timing = {}
	for m in models:
		call(xprompt, m, "Reply with exactly: OK", host, threads, min(ctx, 2048), num_predict=8)
		solo = call(xprompt, m, "Reply with exactly: OK", host, threads, min(ctx, 2048), num_predict=8)
		timing[m] = {"solo_s": solo["wall_s"]}
	concurrent = []
	for r in range(rounds):
		with ThreadPoolExecutor(max_workers=len(models)) as ex:
			futs = [ex.submit(call, xprompt, m, "Reply with exactly: OK", host, threads, min(ctx, 2048), 8) for m in models]
			rows = [f.result() for f in futs]
		concurrent.append({"round": r + 1, "walls": {m: row["wall_s"] for m, row in zip(models, rows)},
			"loadavg": list(os.getloadavg())})
	result = {"models": models, "solo": timing, "concurrent": concurrent,
		"ps_after": api_ps(host), "rounds": rounds}
	with open(os.path.join(out_dir, "concurrency.json"), "w", encoding="utf-8") as f:
		json.dump(result, f, indent=1, sort_keys=True)
	return result

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--models", default=None)
	ap.add_argument("--concurrency", default=None)
	ap.add_argument("--out", required=True)
	ap.add_argument("--xprompt", default=None)
	ap.add_argument("--host", default=None)
	ap.add_argument("--threads", type=int, default=4)
	ap.add_argument("--ctx", type=int, default=8192)
	args = ap.parse_args()
	if not args.models and not args.concurrency:
		fail("pass --models and/or --concurrency")
	xprompt = resolve_xprompt(args.xprompt)
	os.makedirs(args.out, exist_ok=True)
	if args.models:
		for m in [x.strip() for x in args.models.split(",") if x.strip()]:
			r = speed_for_model(xprompt, m, args.out, args.host, args.threads, args.ctx)
			print(f"{m}: " + " | ".join(f"{k} tok/s prefill={v['prefill_tok_s']} gen={v['gen_tok_s']}" for k, v in r["lengths"].items()))
	if args.concurrency:
		models = [x.strip() for x in args.concurrency.split(",") if x.strip()]
		r = concurrency(xprompt, models, args.out, args.host, args.threads, args.ctx)
		print(json.dumps(r["concurrent"], indent=1))

if __name__ == "__main__":
	main()
