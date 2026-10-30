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
	return raw, content

def main():
	raw, content = load_stdout()
	stripped = content.strip()
	parsed = None
	try:
		parsed = json.loads(stripped)
	except (json.JSONDecodeError, ValueError):
		i = stripped.find("{")
		j = stripped.rfind("}")
		if i != -1 and j != -1 and j > i:
			try:
				parsed = json.loads(stripped[i:j+1])
			except (json.JSONDecodeError, ValueError):
				parsed = None
	expected = {"code": "ERROR", "file": "auth.py", "line": 42}
	ok = False
	if isinstance(parsed, dict):
		ok = (parsed.get("code") == expected["code"] and parsed.get("file") == expected["file"] and parsed.get("line") == expected["line"])
	contract_clean = False
	try:
		whole = json.loads(stripped)
		contract_clean = isinstance(whole, dict) and whole.get("code") == expected["code"] and whole.get("file") == expected["file"] and whole.get("line") == expected["line"]
	except (json.JSONDecodeError, ValueError):
		contract_clean = False
	reason = "ok" if ok else "mismatch"
	detail = {"parsed": parsed}
	print(json.dumps({"ok": ok, "contract_clean": contract_clean, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
