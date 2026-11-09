import json,os,sys

def main():
	sandbox = os.getcwd()
	data_dir = os.path.join(sandbox, "data")
	expected = 0
	try:
		for root, _, files in os.walk(data_dir):
			for name in files:
				if name.endswith(".txt"):
					p = os.path.join(root, name)
					with open(p) as f:
						expected += sum(1 for _ in f)
	except FileNotFoundError:
		expected = None
	answer_path = os.path.join(sandbox, "total.txt")
	actual = None
	try:
		with open(answer_path) as f:
			actual = f.read().strip()
	except FileNotFoundError:
		actual = None
	ok = (expected is not None and actual is not None and actual == str(expected))
	reason = "ok" if ok else "mismatch"
	detail = {"expected": expected, "actual": actual}
	print(json.dumps({"ok": ok, "contract_clean": ok, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
EOF
