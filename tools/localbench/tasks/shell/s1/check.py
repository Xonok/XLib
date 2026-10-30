import json,os,sys

def main():
	sandbox = os.getcwd()
	expected_lines = sorted(set())
	names_path = os.path.join(sandbox, "data", "names.txt")
	try:
		with open(names_path) as f:
			lines = [ln.rstrip("\n") for ln in f]
		expected = "".join(x + "\n" for x in sorted(set(ln for ln in lines if ln != "" or True)))
		# unique non-empty? spec: sorted unique lines; keep empty? data has no empty
		expected = "".join(x + "\n" for x in sorted(set(lines)))
	except FileNotFoundError:
		expected = None
	out_path = os.path.join(sandbox, "out", "summary.txt")
	actual = None
	try:
		with open(out_path, "rb") as f:
			actual = f.read()
	except FileNotFoundError:
		actual = None
	ok = (expected is not None and actual is not None and actual == expected.encode())
	reason = "ok" if ok else "mismatch"
	detail = {"expected": expected, "actual": actual.decode() if actual else None}
	print(json.dumps({"ok": ok, "contract_clean": ok, "reason": reason, "detail": detail}))
	sys.exit(0 if ok else 1)

if __name__ == "__main__":
	main()
