import json,os,sys

EXPECTED = {"level": "ERROR", "status": 500, "file": "auth.py", "line": 42}

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

def parse(text):
	stripped = text.strip()
	try:
		return json.loads(stripped)
	except (json.JSONDecodeError, ValueError):
		pass
	i, j = stripped.find("{"), stripped.rfind("}")
	if i >= 0 and j > i:
		try:
			return json.loads(stripped[i:j + 1])
		except (json.JSONDecodeError, ValueError):
			return None
	return None

def same(parsed):
	if not isinstance(parsed, dict):
		return False
	for key, val in EXPECTED.items():
		got = parsed.get(key)
		if key in ("status", "line"):
			try:
				got = int(got)
			except (TypeError, ValueError):
				return False
		if got != val:
			return False
	return True

def main():
	content = load_stdout()
	parsed = parse(content)
	ok = same(parsed)
	contract_clean = False
	try:
		contract_clean = same(json.loads(content.strip()))
	except (json.JSONDecodeError, ValueError):
		contract_clean = False
	print(json.dumps({"ok": ok, "contract_clean": contract_clean,
		"reason": "ok" if ok else "mismatch", "detail": {"parsed": parsed}}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
