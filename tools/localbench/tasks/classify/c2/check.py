import json,os,sys

LABELS = ["feat","fix","docs","test","chore"]
EXPECTED = ["feat","fix","docs","test","chore","feat","fix","docs","test","chore","feat","fix","docs","test","chore","feat","fix","docs","test","chore"]

def load_stdout():
	path = os.environ["LB_STDOUT"]
	with open(path) as f:
		raw = f.read()
	content = raw
	try:
		obj = json.loads(raw)
		if isinstance(obj, dict) and isinstance(obj.get("content"), str):
			content = obj["content"]
	except (json.JSONDecodeError, ValueError):
		pass
	return content

def main():
	content = load_stdout()
	stripped = content.strip()
	lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
	correct = 0
	for i, exp in enumerate(EXPECTED):
		if i < len(lines) and lines[i] == exp:
			correct += 1
	ok = correct >= 18
	contract_clean = (len(lines) == 20 and all(ln in LABELS for ln in lines))
	reason = "ok" if ok else "mismatch"
	detail = {"correct": correct, "lines": len(lines)}
	print(json.dumps({"ok": ok, "contract_clean": contract_clean, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
