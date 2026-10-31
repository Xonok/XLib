#!/usr/bin/env python3
"""localbench ledger: one row per run, generated from meta.json files.

    ledger.py --runs DIR --out ledger.jsonl --markdown corpus.md [--check]

The runs directory holds one subdirectory per run, each with meta.json and (unless the
run was made with --no-final) a final/ copy of the sandbox. --check re-runs every
checker against that stored state in a throwaway copy, so a checker change is visible
as a disagreement rather than silently changing a historical result.
"""
import argparse,json,os,shutil,statistics,subprocess,sys,tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS_DEFAULT = ROOT / "tasks"

def median(values):
	vals = [v for v in values if isinstance(v, (int, float))]
	return round(statistics.median(vals), 3) if vals else None

def load_meta(path):
	try:
		return json.loads(path.read_text())
	except (OSError, json.JSONDecodeError):
		return None

def find_runs(runs_dir):
	out = []
	for meta_path in sorted(Path(runs_dir).rglob("meta.json")):
		meta = load_meta(meta_path)
		if isinstance(meta, dict):
			meta["_meta_path"] = str(meta_path)
			out.append(meta)
	out.sort(key=lambda m: (m.get("started") or "", m.get("model") or "", m.get("task") or "", m.get("case") or "", m.get("repeat") or 0, m.get("_meta_path")))
	return out

def write_jsonl(rows, out_path):
	lines = [json.dumps({k: v for k, v in row.items() if k != "_meta_path"}, sort_keys=True) for row in rows]
	Path(out_path).write_text("".join(line + "\n" for line in lines))

def recheck(row, tasks_dir):
	meta_path = Path(row["_meta_path"])
	final_dir = meta_path.parent / "final"
	if not final_dir.is_dir():
		return {"state_missing": True}
	task_dir = Path(tasks_dir) / str(row.get("task")) / str(row.get("case"))
	check = task_dir / "check.py"
	if not check.is_file():
		return {"checker_missing": True}
	tmp = Path(tempfile.mkdtemp(prefix="localbench-check-"))
	try:
		sandbox = tmp / "sandbox"
		shutil.copytree(final_dir, sandbox)
		env = {**os.environ,
			"LB_STDOUT": str(meta_path.parent / "stdout.txt"),
			"LB_TASK_DIR": str(task_dir),
			"LB_META": str(meta_path)}
		proc = subprocess.run([sys.executable, str(check)], cwd=str(sandbox), env=env, capture_output=True, text=True, timeout=120)
		if proc.returncode == 2 or not proc.stdout.strip():
			return {"checker_error": True, "returncode": proc.returncode, "stderr": proc.stderr[-500:]}
		try:
			parsed = json.loads(proc.stdout.strip().splitlines()[-1])
		except (json.JSONDecodeError, ValueError):
			return {"checker_error": True, "returncode": proc.returncode}
		return {"ok": bool(parsed.get("ok")), "contract_clean": bool(parsed.get("contract_clean")), "reason": str(parsed.get("reason", ""))}
	finally:
		shutil.rmtree(tmp, ignore_errors=True)

def check_rows(rows, tasks_dir):
	disagreements, missing, errors = [], [], []
	truncated = []
	for row in rows:
		if row.get("truncated"):
			truncated.append(row)
			continue
		result = recheck(row, tasks_dir)
		if result.get("state_missing"):
			missing.append(row)
			continue
		if result.get("checker_error"):
			errors.append((row, result))
			continue
		stored = row.get("checker") or {}
		if result.get("ok") != stored.get("ok") or result.get("contract_clean") != stored.get("contract_clean"):
			disagreements.append((row, stored, result))
	for row in missing:
		print(f"state_missing: {row.get('model')} {row.get('task')}/{row.get('case')} r{row.get('repeat')} ({row['_meta_path']})")
	for row, result in errors:
		print(f"checker_error: {row.get('model')} {row.get('task')}/{row.get('case')} r{row.get('repeat')}: {result}")
	for row, stored, result in disagreements:
		print(f"DISAGREE: {row.get('model')} {row.get('task')}/{row.get('case')} r{row.get('repeat')}: stored ok={stored.get('ok')} contract={stored.get('contract_clean')} -> now ok={result.get('ok')} contract={result.get('contract_clean')}")
	print(f"check: {len(rows)} rows, {len(rows) - len(truncated) - len(missing) - len(errors) - len(disagreements)} agree, {len(disagreements)} disagree, {len(missing)} state_missing, {len(errors)} checker_error, {len(truncated)} truncated (not re-checked)")
	return 1 if disagreements or errors else 0

def markdown(rows):
	groups = {}
	for row in rows:
		bench = str(row.get("bench_version") or "")[:13]
		key = (str(row.get("model")), str(row.get("task")), bench)
		groups.setdefault(key, []).append(row)
	lines = [
		"<!-- BEGIN GENERATED: localbench -->",
		"| Model | Family | bench | n | pass | contract | median wall s | prefill tok/s | gen tok/s | native/parsed calls | trunc |",
		"|---|---|---|---|---|---|---|---|---|---|---|",
	]
	for (model, family, bench) in sorted(groups):
		items = groups[(model, family, bench)]
		live = [r for r in items if not r.get("truncated")]
		truncs = len(items) - len(live)
		n = len(live)
		passes = sum(1 for r in live if (r.get("checker") or {}).get("ok"))
		contracts = sum(1 for r in live if (r.get("checker") or {}).get("contract_clean"))
		wall = median([r.get("wall_time_s") for r in live])
		prefill = median([r.get("prefill_tok_s") for r in live])
		gen = median([r.get("gen_tok_s") for r in live])
		native = sum(1 for r in live for c in (r.get("tool_calls") or []) if c.get("source") == "native")
		parsed = sum(1 for r in live for c in (r.get("tool_calls") or []) if c.get("source") == "parsed")
		lines.append(f"| {model} | {family} | {bench} | {n} | {passes} | {contracts} | {wall if wall is not None else '-'} | {prefill if prefill is not None else '-'} | {gen if gen is not None else '-'} | {native}/{parsed} | {truncs} |")
	lines.append("<!-- END GENERATED: localbench -->")
	return "\n".join(lines) + "\n"

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--runs", required=True)
	ap.add_argument("--out", default=None)
	ap.add_argument("--markdown", default=None)
	ap.add_argument("--tasks", default=str(TASKS_DEFAULT))
	ap.add_argument("--check", action="store_true")
	args = ap.parse_args()
	rows = find_runs(args.runs)
	if args.out:
		write_jsonl(rows, args.out)
	if args.markdown:
		Path(args.markdown).write_text(markdown(rows))
	if args.check:
		sys.exit(check_rows(rows, args.tasks))
	if not args.out and not args.markdown:
		print(f"{len(rows)} row(s); use --out and/or --markdown")

if __name__ == "__main__":
	main()
