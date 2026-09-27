"""Benchmark runner. Resumable, append-only, and it never lets an infrastructure
failure be scored as a model failure.

A run is one JSONL file. Each line is either a task record or a judgement record, tagged
with `kind`. Because the file is append-only and flushed per line, a run killed by a
timeout, a rate limit or a crash resumes by skipping (task_id, repeat) pairs already
present — nothing already paid for is paid for twice.
"""

import argparse,json,os,score,time,transport

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(HERE,"prompts","evaluation")
# Defaults follow the tool, not the caller's cwd — the tool is invoked from anywhere, and
# a path relative to cwd silently scores the wrong (or no) suite.
REGISTRY = os.path.join(HERE,"models.toml")
TASKS = os.path.join(HERE,"tasks","anchors","suite.jsonl")

def load_registry(path):
	# tomllib is stdlib from 3.11; this box runs 3.14. Kept in a function so the import
	# cost and the failure mode are both visible at the call site.
	import tomllib
	with open(path,"rb") as f:
		return tomllib.load(f)

def load_tasks(path):
	tasks = []
	with open(path) as f:
		for line in f:
			line = line.strip()
			if line:
				tasks.append(json.loads(line))
	return tasks

def read_done(path):
	done = set()
	for kind,rec in _records(path):
		if rec.get("kind") == "judgement":
			done.add((rec["task_id"],rec["repeat"]))
	return done

def _records(path):
	# Tolerates a missing file: every caller is asking "what is already in this run",
	# and on a first run the answer is legitimately nothing.
	if not os.path.exists(path):
		return
	with open(path) as f:
		for line in f:
			line = line.strip()
			if not line:
				continue
			try:
				yield line.split("\t")[0],json.loads(line.split("\t",1)[-1])
			except (json.JSONDecodeError,IndexError):
				continue

def judge_prompt(category):
	path = os.path.join(PROMPTS,f"{category}.md")
	if not os.path.exists(path):
		raise KeyError(f"no judge prompt registered for category {category!r} (F9: unmapped categories must fail loudly, not skip silently)")
	with open(path) as f:
		return f.read()

def render_task_prompt(task):
	parts = [task["context"].strip(),""]
	if task.get("question"):
		parts += [f"QUESTION: {task['question']}"]
	if task.get("questions"):
		parts += ["QUESTIONS:"] + [f"  {i+1}. {q}" for i,q in enumerate(task["questions"])]
	parts += ["", "Answer directly. No preamble, no restatement of the question."]
	return "\n".join(parts)

def render_judge_prompt(task,response):
	tmpl = judge_prompt(task["category"])
	return tmpl.replace("{{TASK_JSON}}",json.dumps(task,indent=2)).replace("{{RESPONSE}}",response)

def parse_judge_json(text):
	"""Strict on purpose. A judge that rambles has produced an unjudgeable result, and
	coaxing it into shape by hand is how a bad grade becomes a good one."""
	start = text.find("{")
	if start < 0:
		return None
	depth,in_str,esc = 0,False,False
	for i,ch in enumerate(text[start:],start):
		if esc:
			esc = False
			continue
		if ch == "\\":
			esc = True
			continue
		if ch == '"':
			in_str = not in_str
			continue
		if in_str:
			continue
		if ch == "{":
			depth += 1
		elif ch == "}":
			depth -= 1
			if depth == 0:
				try:
					return json.loads(text[start:i+1])
				except json.JSONDecodeError:
					return None
	return None

def run(args):
	registry = load_registry(args.registry)
	bad = transport.validate_registry(registry)
	if bad:
		raise SystemExit("registry invalid:\n  " + "\n  ".join(bad))
	if args.model not in registry:
		raise SystemExit(f"unknown model {args.model!r}; known: {', '.join(sorted(registry))}")
	if args.judge not in registry:
		raise SystemExit(f"unknown judge {args.judge!r}")
	model,judge = registry[args.model],registry[args.judge]
	if model["id"] == judge["id"] and not args.allow_self_judge:
		raise SystemExit(f"refusing to run: {args.model} would judge itself (B3). Pass --allow-self_judge to override; the report will still be marked self_judged.")

	tasks = load_tasks(args.tasks)
	os.makedirs(os.path.dirname(args.out) or ".",exist_ok=True)
	done = read_done(args.out)
	seen_tasks = {rec["id"] for rec in _records(args.out) if rec.get("kind") == "task"}
	os.makedirs("/tmp/opencode/bench-run",exist_ok=True)
	fh = open(args.out,"a")

	for task in tasks:
		# Re-appending the task record on every resume grows the file for no gain; the
		# scoring side keys on task_id, but a run file that grows on each retry is a
		# run file nobody can read.
		if task["id"] not in seen_tasks:
			fh.write("task\t"+json.dumps(task)+"\n")
			fh.flush()
			seen_tasks.add(task["id"])
		prompt = render_task_prompt(task)
		for rep in range(args.repeats):
			if (task["id"],rep) in done:
				continue
			try:
				out = transport.call_model(model,prompt,max_tokens=args.max_tokens)
			except Exception as e:
				# Recorded as an error, never as a model failure: an unreachable model and a
				# model that got the question wrong must not land in the same bucket.
				rec = {"kind":"judgement","task_id":task["id"],"repeat":rep,"category":task["category"],
					"error":str(e)[:300],"passed":None,"scores":{},"failure_modes":[]}
				fh.write("judgement\t"+json.dumps(rec)+"\n")
				fh.flush()
				print(f"  ERROR {task['id']} rep{rep}: {str(e)[:80]}",flush=True)
				continue
			jout = {"text":""}
			verdict = None
			try:
				jout = transport.call_model(judge,render_judge_prompt(task,out["text"]),max_tokens=args.judge_max_tokens)
				verdict = parse_judge_json(jout["text"])
			except Exception as e:
				# A judge that cannot be reached is a hole in the run, not a model failure.
				print(f"  judge error {task['id']} rep{rep}: {str(e)[:80]}",flush=True)
			rec = {"kind":"judgement","task_id":task["id"],"repeat":rep,"category":task["category"],
				"model_id":model["id"],"judge_id":judge["id"],"repeats":args.repeats,
				"passed":score.apply_pass_rule(task["category"],(verdict or {}).get("scores",{})) if verdict else None,
				"scores":(verdict or {}).get("scores",{}),
				"failure_modes":(verdict or {}).get("failure_modes",[]) or [],
				"judge_note":(verdict or {}).get("note"),
				"response":out["text"],"reasoning":out["reasoning"],
				"judge_raw":None if verdict else jout["text"][:2000]}
			fh.write("judgement\t"+json.dumps(rec)+"\n")
			fh.flush()
			print(f"  {task['id']} rep{rep} pass={rec['passed']} ({out['transport']})",flush=True)
			time.sleep(args.pause)
	fh.close()

def main():
	p = argparse.ArgumentParser(description="Run the model benchmark suite")
	p.add_argument("--model",required=True)
	p.add_argument("--judge",default="big-pickle")
	p.add_argument("--tasks",default=TASKS)
	p.add_argument("--registry",default=REGISTRY)
	p.add_argument("--out",required=True)
	p.add_argument("--repeats",type=int,default=3)
	p.add_argument("--max-tokens",type=int,default=2048)
	p.add_argument("--judge-max-tokens",type=int,default=2048)
	p.add_argument("--pause",type=float,default=1.0)
	p.add_argument("--allow-self-judge",action="store_true")
	run(p.parse_args())

if __name__ == "__main__":
	main()
