import json,os,re,sys

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

EXPECTED = '30'

def main():
	content = load_stdout().strip()
	ok = bool(re.search(r"\b" + re.escape(EXPECTED) + r"\b", content))
	contract_clean = (content == EXPECTED)
	reason = "ok" if ok else "mismatch"
	detail = {"stdout": content}
	print(json.dumps({"ok": ok, "contract_clean": contract_clean, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
