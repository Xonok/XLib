import json,os,re,sys
from decimal import Decimal,InvalidOperation

EXPECTED_VENDOR = "Acme Supplies Ltd"
EXPECTED_INVOICE = "INV-2024-0892"
EXPECTED_DUE = "2024-11-15"
# compared as a number: 1240.5 and "1,240.50" are the same total, and the prompt asks for
# the field's value, not a particular rendering of it
EXPECTED_TOTAL = Decimal("1240.50")

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

def same_total(v):
	stripped = re.sub(r"[^0-9.]", "", str(v))
	if not stripped:
		return False
	try:
		return Decimal(stripped) == EXPECTED_TOTAL
	except InvalidOperation:
		return False

def matches(obj):
	if not isinstance(obj, dict):
		return False
	return (
		obj.get("vendor") == EXPECTED_VENDOR
		and obj.get("invoice") == EXPECTED_INVOICE
		and obj.get("due") == EXPECTED_DUE
		and same_total(obj.get("total"))
	)

def parse(text):
	stripped = text.strip()
	try:
		return json.loads(stripped)
	except (json.JSONDecodeError, ValueError):
		pass
	i, j = stripped.find("{"), stripped.rfind("}")
	if i < 0 or j <= i:
		return None
	try:
		return json.loads(stripped[i:j + 1])
	except (json.JSONDecodeError, ValueError):
		return None

def main():
	raw, content = load_stdout()
	parsed = parse(content)
	ok = matches(parsed)
	# contract_clean means the output itself parses whole and is right — no fence, no prose
	try:
		contract_clean = matches(json.loads(content.strip()))
	except (json.JSONDecodeError, ValueError):
		contract_clean = False
	print(json.dumps({"ok": ok, "contract_clean": contract_clean,
		"reason": "ok" if ok else "mismatch", "detail": {"parsed": parsed}}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
