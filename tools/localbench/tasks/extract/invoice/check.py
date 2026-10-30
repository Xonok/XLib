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
	return raw, content

def normalize_total(v):
	s = str(v)
	return re.sub(r"[^0-9.]", "", s)

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
	expected = {"vendor": "Acme Supplies Ltd", "invoice": "INV-2024-0892", "due": "2024-11-15", "total": "1240.50"}
	ok = False
	if isinstance(parsed, dict):
		ok = (
			parsed.get("vendor") == expected["vendor"]
			and parsed.get("invoice") == expected["invoice"]
			and parsed.get("due") == expected["due"]
			and normalize_total(parsed.get("total")) == expected["total"]
		)
	contract_clean = False
	try:
		whole = json.loads(stripped)
		contract_clean = isinstance(whole, dict) and whole == parsed and parsed is not None
	except (json.JSONDecodeError, ValueError):
		contract_clean = False
	# stricter: contract_clean means stripped itself parses and matches expected
	try:
		whole = json.loads(stripped)
		contract_clean = isinstance(whole, dict) and normalize_total(whole.get("total", "")) == expected["total"] and whole.get("vendor") == expected["vendor"] and whole.get("invoice") == expected["invoice"] and whole.get("due") == expected["due"]
	except (json.JSONDecodeError, ValueError):
		contract_clean = False
	reason = "ok" if ok else "mismatch"
	detail = {"parsed": parsed}
	print(json.dumps({"ok": ok, "contract_clean": contract_clean, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
