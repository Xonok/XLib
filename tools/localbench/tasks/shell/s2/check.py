import json,os,sys

def main():
	sandbox = os.getcwd()
	data_dir = os.path.join(sandbox, "data")
	expected = None
	try:
		entries = []
		for name in os.listdir(data_dir):
			p = os.path.join(data_dir, name)
			if os.path.isfile(p):
				entries.append((name, os.path.getsize(p)))
		if entries:
			expected = max(entries, key=lambda x: x[1])[0]
	except FileNotFoundError:
		expected = None
	answer_path = os.path.join(sandbox, "answer.txt")
	actual = None
	try:
		with open(answer_path) as f:
			actual = f.read().strip()
	except FileNotFoundError:
		actual = None
	ok = (expected is not None and actual == expected)
	reason = "ok" if ok else "mismatch"
	detail = {"expected": expected, "actual": actual}
	print(json.dumps({"ok": ok, "contract_clean": ok, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
