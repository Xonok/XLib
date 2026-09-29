import argparse,collections,glob,json,os,sys,tomllib

sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modelbench import agent,trace

HERE = os.path.dirname(os.path.abspath(__file__))
EPISODES = os.path.join(HERE,"episodes")
REGISTRY = os.path.join(HERE,"models.toml")

def load_short_names():
	"""Provider id -> the short name the registry calls it.

	A trace records the model as its provider id, which is the id that was actually
	called. The short name is what the registry and every document use, and a ledger
	whose model column is a provider id forces a reader to translate it on every row.
	"""
	out = {}
	if not os.path.exists(REGISTRY):
		return out
	with open(REGISTRY,"rb") as fh:
		for short,spec in tomllib.load(fh).items():
			if spec.get("id"):
				out[spec["id"]] = short
	return out

SHORT = {}
# The re-grade verdict is a diagnostic about the *grader*, not a property of the run, so it
# is never written into the ledger. Keeping it out is what makes the file idempotent.
REGREDED = {}

def _sort_key(row):
	return (row["date"] or "",row["model"] or "",row["episode"] or "",
		str(row["repeat"]),row["src"],row["line"])

def _short_name(model_id):
	return SHORT.get(model_id,model_id) if model_id else model_id

def _count_turns(rec):
	t = rec.get("trace")
	return len(t.get("turns") or []) if isinstance(t,dict) else 0

def _state_dir(root,src,row):
	"""The retained final on-disk state for a run, if it was kept.

	Beside the trace, not under a shared state/ directory, because each run wave keeps its
	own copy. This is what makes a re-grade possible at all: analyse() reads the model's
	final files through trace['root'], so turns alone cannot reproduce a grade. A record
	whose sandbox is gone therefore cannot be re-graded even when it stored its turns —
	which is the second half of why the state has to be kept, not just the turns.
	"""
	repeat = row["repeat"] if row["repeat"] is not None else 0
	guess = os.path.join(root,os.path.dirname(src),"state",
		f'{row["model"]}--{row["episode"]}--{repeat}')
	return guess if os.path.isdir(guess) else None

def _baselines():
	"""The pristine checker result per episode, recomputed rather than stored.

	G3 and G6 both ask what was true *before* the model touched anything, which is a
	property of the episode, not of a run — so one baseline per episode is enough, and
	recomputing it means a ledger can be rebuilt years later with no stored state. It
	is only equal to the original if the episode is unchanged, and an episode change
	moves bench_version, which every row carries.
	"""
	out = {}
	for name in sorted(os.listdir(EPISODES)):
		d = os.path.join(EPISODES,name)
		if os.path.isfile(os.path.join(d,"check.py")):
			out[name] = trace.check_episode(d)[1]
	return out

def _row(root,src,line,rec,baselines):
	detail = rec.get("detail") or {}
	checker = detail.get("checker") or {}
	model_id = rec.get("model")
	date = src.split(os.sep)[0] if os.sep in src else ""
	row = {"src":src,"line":line,"date":date,
		"model":_short_name(model_id),"model_id":model_id,
		"episode":rec.get("episode"),"repeat":rec.get("repeat"),
		"transport":(rec.get("provenance") or {}).get("transport") or rec.get("transport"),
		"grade":rec.get("grade"),"gates":rec.get("gates"),
		"failed_gates":rec.get("failed_gates"),
		"bench_version":rec.get("bench_version"),"grade_version":rec.get("grade_version"),
		"n_turns":detail.get("n_turns"),"n_writes":detail.get("n_writes"),
		"n_runs":detail.get("n_runs"),"tokens":detail.get("tokens"),
		"cases":len(checker.get("cases") or []),
		"claim":detail.get("claim"),"declared_status":detail.get("declared_status"),
		"turns_stored":_count_turns(rec) > 0}
	row["state_stored"] = _state_dir(root,src,row) is not None
	# The standing audit, applied to every row so a hole in a run can never be read as a
	# result: an empty case set is a dead checker, zero turns is a run that produced
	# nothing, and a missing grade is a rate limit or a crash. None of them is a model.
	row["admitted"] = bool(row["grade"]) and row["cases"] > 0 and bool(row["n_turns"])
	if args.check and row["turns_stored"]:
		base = baselines.get(rec.get("episode"))
		state = _state_dir(root,src,row)
		if base is None:
			row["regrade"] = "no episode to baseline against"
		elif state is None:
			row["regrade"] = "final state not kept"
		else:
			try:
				raw = dict(rec["trace"])
				raw["root"] = state
				g,_ = trace.grade(trace.analyse(raw,baseline=base))
				REGREDED[id(row)] = g
			except Exception as exc:
				REGREDED[id(row)] = f"error: {exc}"
	return row

def read_all(root):
	for path in sorted(glob.glob(os.path.join(root,"**","*.jsonl"),recursive=True)):
		src = os.path.relpath(path,root)
		with open(path) as fh:
			for line,text in enumerate(fh,1):
				text = text.strip()
				if not text:
					continue
				try:
					yield src,line,json.loads(text)
				except json.JSONDecodeError as exc:
					print(f"  ! {src}:{line} is not JSON ({exc})",file=sys.stderr)

def summarise(rows):
	print(f"{len(rows)} records, {sum(r['turns_stored'] for r in rows)} carrying raw turns, "
		f"{sum(r['admitted'] for r in rows)} admitted by the standing audit")
	by = collections.Counter((r["model"],r["episode"],r["grade"]) for r in rows)
	for (model,ep,grade),n in sorted(by.items(),key=lambda kv:[(str(x or "")) for x in kv[0]]):
		print(f"  {n:3d}  {model:26s} {str(ep or '-'):10s} {str(grade or 'NO GRADE')}")
	per_model = collections.Counter(r["model"] for r in rows)
	print("\nrecords per model:")
	for model,n in sorted(per_model.items(),key=lambda kv:-kv[1]):
		print(f"  {n:3d}  {model}")
	lost = [r for r in rows if not r["turns_stored"]]
	if lost:
		print(f"\n{len(lost)} of {len(rows)} records cannot be re-graded: the turns were not stored. "
			"Any change to a gate costs a re-measurement of every one of these.")
	holes = [r for r in rows if not r["admitted"]]
	if holes:
		print(f"{len(holes)} of {len(rows)} are holes rather than results "
			"(no grade, dead checker, or a run that produced nothing):")
		for r in holes[:20]:
			print(f"  {r['src']}:{r['line']} {r['model']} {r['episode']} "
				f"grade={r['grade']} cases={r['cases']} turns={r['n_turns']}")
	if args.check:
		verifiable = [r for r in rows if id(r) in REGREDED]
		drift = [r for r in verifiable if REGREDED[id(r)] != r["grade"]]
		skipped = [r for r in rows if r["turns_stored"] and id(r) not in REGREDED]
		print(f"\nre-grade: {len(drift)} of {len(verifiable)} verifiable records disagree "
			"with the stored grade")
		for r in drift:
			print(f"  {r['src']}:{r['line']} {r['model']} {r['episode']} "
				f"stored={r['grade']} now={REGREDED[id(r)]}")
		for r in skipped:
			print(f"  ! {r['src']}:{r['line']} {r['model']} {r['episode']} could not be re-graded")

def as_markdown(rows):
	"""The per-model table, rendered from the ledger.

	Exists so a document can quote the corpus without anyone retyping a count. Every
	figure here is a row above, so a corrected count costs one script run and a stale
	one cannot survive in prose.
	"""
	out = ["| Model | Episode | Grade | n | Admissible | Raw turns |","|---|---|---|---|---|---|"]
	by = collections.Counter((r["model"],r["episode"],r["grade"]) for r in rows)
	for (model,ep,grade),n in sorted(by.items(),key=lambda kv:[(str(x or "")) for x in kv[0]]):
		same = [r for r in rows if r["model"] == model and r["episode"] == ep and r["grade"] == grade]
		adm = sum(r["admitted"] for r in same)
		tur = sum(r["turns_stored"] for r in same)
		out.append(f"| {model} | {ep or '—'} | {grade or '**no grade**'} | {n} | "
			f"{adm} | {tur} |")
	return "\n".join(out)

def main():
	global args
	p = argparse.ArgumentParser(description=__doc__)
	p.add_argument("--traces",required=True,help="root of the run-wave directories")
	p.add_argument("--out",help="write the ledger here; without it the summary is printed only")
	p.add_argument("--markdown",help="write the per-model table here, generated from the ledger")
	p.add_argument("--check",action="store_true",
		help="re-grade every record that stored its turns and report the disagreements")
	args = p.parse_args()
	SHORT.update(load_short_names())
	root = args.traces
	baselines = _baselines() if args.check else {}
	rows = sorted((_row(root,src,line,rec,baselines) for src,line,rec in read_all(root)),
		key=_sort_key)
	# Append-only in effect: a re-run over the same traces produces the same bytes, so the
	# ledger is a generated file rather than something anyone edits and then retypes.
	if args.out:
		os.makedirs(os.path.dirname(os.path.abspath(args.out)),exist_ok=True)
		with open(args.out,"w") as fh:
			for row in rows:
				fh.write(json.dumps(row,sort_keys=True)+"\n")
		print(f"wrote {len(rows)} rows to {args.out}")
	if args.markdown:
		os.makedirs(os.path.dirname(os.path.abspath(args.markdown)),exist_ok=True)
		with open(args.markdown,"w") as fh:
			fh.write(as_markdown(rows)+"\n")
		print(f"wrote the per-model table to {args.markdown}")
	summarise(rows)

if __name__ == "__main__":
	main()
