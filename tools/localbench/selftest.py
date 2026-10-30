import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"

def copytree(src, dst):
	if src.exists():
		shutil.copytree(src, dst, dirs_exist_ok=True)

def run_check(case_dir, sandbox, stdout_path):
	env = os.environ.copy()
	env["LB_STDOUT"] = str(stdout_path)
	env["LB_TASK_DIR"] = str(case_dir)
	env["LB_META"] = str(sandbox.parent / "meta.json")
	r = subprocess.run([sys.executable, str(case_dir / "check.py")], cwd=str(sandbox), env=env, capture_output=True, text=True, timeout=120)
	parsed = None
	try:
		parsed = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None
	except (json.JSONDecodeError, ValueError):
		parsed = None
	return r, parsed

def main():
	failures = []
	total = 0
	for family_dir in sorted(TASKS.iterdir()):
		if not family_dir.is_dir():
			continue
		for case_dir in sorted(family_dir.iterdir()):
			if not case_dir.is_dir() or not (case_dir / "task.json").exists():
				continue
			task = json.loads((case_dir / "task.json").read_text())
			kind = task["kind"]
			has_fixture = (case_dir / "fixture").exists()
			for scenario in ("reference", "broken", "empty"):
				total += 1
				td = Path(tempfile.mkdtemp())
				sandbox = td / "sandbox"
				sandbox.mkdir()
				if scenario != "empty" and has_fixture:
					copytree(case_dir / "fixture", sandbox)
				if scenario == "reference":
					if (case_dir / "reference").exists():
						copytree(case_dir / "reference", sandbox)
					stdout_content = (case_dir / "reference.txt").read_text() if (case_dir / "reference.txt").exists() else ""
				elif scenario == "broken":
					if (case_dir / "broken").exists():
						copytree(case_dir / "broken", sandbox)
					stdout_content = (case_dir / "broken.txt").read_text() if (case_dir / "broken.txt").exists() else ""
				else:
					stdout_content = ""
				stdout_path = td / "stdout.txt"
				stdout_path.write_text(stdout_content)
				r, parsed = run_check(case_dir, sandbox, stdout_path)
				expected_pass = (scenario == "reference")
				ok_val = bool(parsed.get("ok")) if isinstance(parsed, dict) else False
				status = "PASS" if (ok_val == expected_pass) else "FAIL"
				if scenario == "reference" and isinstance(parsed, dict) and not parsed.get("contract_clean", False):
					status = "FAIL"
					print(f"  contract_clean false for reference: {family_dir.name}/{case_dir.name}")
				if status == "FAIL":
					failures.append((family_dir.name, case_dir.name, scenario, r.returncode, r.stdout, r.stderr))
					print(f"FAIL {family_dir.name}/{case_dir.name} [{scenario}] rc={r.returncode} ok={ok_val} expected_pass={expected_pass}")
					if r.stderr.strip():
						print(r.stderr.strip())
				else:
					print(f"ok   {family_dir.name}/{case_dir.name} [{scenario}]")
	shutil.rmtree(td, ignore_errors=True)
	print(f"\nselftest: {total - len(failures)}/{total} passed")
	if failures:
		print(f"{len(failures)} failure(s)")
		sys.exit(1)
	print("all green")

if __name__ == "__main__":
	main()
