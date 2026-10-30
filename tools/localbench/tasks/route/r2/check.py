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

EXPECTED = 'run_tests'

def main():
	content = load_stdout().strip()
	ok = content == EXPECTED
	print(json.dumps({"ok": ok, "contract_clean": ok, "reason": "ok" if ok else "mismatch", "detail": {"stdout": content}}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
