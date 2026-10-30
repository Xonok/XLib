import json,os,sys

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
	content = load_stdout().strip()
	expected = {"status": "ready", "count": 3}
	parsed = None
	try:
		parsed = json.loads(content)
	except (json.JSONDecodeError, ValueError):
		parsed = None
	ok = parsed == expected
	contract_clean = parsed == expected
	print(json.dumps({"ok": ok, "contract_clean": contract_clean, "reason": "ok" if ok else "mismatch", "detail": {"parsed": parsed}}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
