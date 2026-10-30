import json,os,sys

EXPECTED = {"sender": "jane.doe@example.com", "current_deadline": "2024-12-01",
	"requested_deadline": "2024-12-15", "intent": "extend"}

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

def main():
	content = load_stdout()
	parsed = parse(content)
	ok = isinstance(parsed, dict) and all(parsed.get(k) == v for k, v in EXPECTED.items())
	contract_clean = False
	try:
		whole = json.loads(content.strip())
		contract_clean = isinstance(whole, dict) and all(whole.get(k) == v for k, v in EXPECTED.items())
	except (json.JSONDecodeError, ValueError):
		contract_clean = False
	print(json.dumps({"ok": ok, "contract_clean": contract_clean,
		"reason": "ok" if ok else "mismatch", "detail": {"parsed": parsed}}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
