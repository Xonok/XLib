import json,os,sys

FACTS = [
	("database outage", ("database outage",)),
	("2 hours", ("2 hours", "two hours", "2-hour", "two-hour")),
	("misconfigured index", ("misconfigured index",)),
	("1,200 users", ("1,200 users",)),
	("resolved by rollback", ("rollback", "rolling back", "rolled back")),
]

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
	# strip code fences for fence detection
	fenced = "```" in content
	words = content.split()
	wc = len(words)
	lower = content.lower()
	missing = [label for label, alternatives in FACTS if not any(a in lower for a in alternatives)]
	ok = (wc <= 60 and len(missing) == 0)
	contract_clean = (not fenced and wc <= 60)
	reason = "ok" if ok else "mismatch"
	detail = {"word_count": wc, "missing": missing}
	print(json.dumps({"ok": ok, "contract_clean": contract_clean, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
