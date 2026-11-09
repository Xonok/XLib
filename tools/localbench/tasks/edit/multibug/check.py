import json,os,subprocess,sys,glob

def main():
	sandbox = os.getcwd()
	tests = sorted(glob.glob(os.path.join(sandbox, "test_*.py")))
	outputs = []
	ok = True
	for t in tests:
		try:
			r = subprocess.run(["python3", t], cwd=sandbox, capture_output=True, text=True, timeout=120)
		except Exception as e:
			ok = False
			outputs.append({"test": os.path.basename(t), "error": str(e)})
			continue
		outputs.append({"test": os.path.basename(t), "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr})
		if r.returncode != 0:
			ok = False
	if not tests:
		ok = False
	reason = "ok" if ok else "tests failed"
	detail = {"tests": outputs}
	print(json.dumps({"ok": ok, "contract_clean": True, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
