import os,re,subprocess,sys,tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bundler import bundle

FIX = os.path.join(ROOT, "test", "fixtures")

asserts = {
	"single": (
		[r"def helper_area", r"def helper_shadow", r"helper_piq = 3\.0",
		 r"from file: helper\.py"],
		[r"import helper", r"helper_piq = 10\.0", r"def area"],
	),
	"nested": (
		[r"server_Analysis_itemcount_run", r"server_Analysis_itemcount_more",
		 r"server_Analysis_itemcount_count = 41", r"server_defs_items",
		 r"server_defs_label = \"one\"", r"server_defs_show",
		 r"server_io_save", r"server_io_saved = \"io-ran\"",
		 r"from file: server/defs\.py", r"from file: server/io\.py"],
		[r"from server import", r"import server\b", r"from \. import itemcount",
		 r"^label = \"one\"", r"^count = 41", r"^saved = \"io-ran\""],
	),
	"collision": (
		[r"def a_run", r"def b_run", r"a_tag = \"A\"", r"b_tag = \"B\""],
		[r"\btag = \"A\"", r"\btag = \"B\"", r"import a\b", r"import b\b"],
	),
	"alias": (
		[r"def util_connect", r"def util_ping", r"import random as rr"],
		[r"def connect", r"from util import", r"\blink\b", r"\bping\b"],
	),
	"rel": (
		[r"def pkg_top_run", r"def pkg_peer_who", r"pkg_top_run\(\)"],
		[r"from \. import", r"import pkg\.top"],
	),
	"deep": (
		[r"db_model_Connection", r"def db_core_create_conn",
		 r"from file: db/model\.py"],
		[r"from db import (model|core)"],
	),
	"stdlib": (
		[r"from urllib\.parse import urlparse", r"import json,collections",
		 r"from collections import defaultdict",
		 r"import math as m"],
		[],
	),
}

order_before = {
	"nested": [(r"from file: server/defs\.py", r"from file: server/io\.py")],
	"deep": [(r"from file: db/model\.py", r"from file: db/core\.py")],
}

entry_names = {"nested": "server.py"}

def run_file(path, cwd):
	return subprocess.run([sys.executable, path], cwd=cwd, capture_output=True, text=True)

def check_text(name, text):
	must, must_not = asserts[name]
	bad = []
	for pat in must:
		if not re.search(pat, text):
			bad.append("missing: " + pat)
	for pat in must_not:
		if re.search(pat, text):
			bad.append("unexpected: " + pat)
	for first, second in order_before.get(name, []):
		if not re.search(first, text) or not re.search(second, text):
			continue
		if text.find(first, 0) > text.find(second):
			bad.append("order: %s must come before %s" % (first, second))
	return bad

def main():
	failed = 0
	for name in sorted(os.listdir(FIX)):
		d = os.path.join(FIX, name)
		entry = os.path.join(d, entry_names.get(name, "main.py"))
		if not os.path.isfile(entry):
			continue
		orig = run_file(entry, d)
		try:
			text = bundle(entry)
		except Exception as e:
			print("CRASH %s: %r" % (name, e))
			failed += 1
			continue
		issues = check_text(name, text)
		with tempfile.TemporaryDirectory() as tmp:
			out = os.path.join(tmp, "main.py")
			with open(out, "w") as f:
				f.write(text)
			got = run_file(out, tmp)
		ok = orig.returncode == 0 and got.returncode == 0 and orig.stdout == got.stdout
		if issues:
			print("ASSERT %s: %s" % (name, "; ".join(issues)))
			failed += 1
		if not ok:
			print("MISMATCH %s" % name)
			print("  original rc=%d out=%r err=%r" % (orig.returncode, orig.stdout, orig.stderr))
			print("  bundled  rc=%d out=%r err=%r" % (got.returncode, got.stdout, got.stderr))
			failed += 1
		print("%s %s" % ("FAIL" if issues or not ok else "pass", name))
	return failed

if __name__ == "__main__":
	sys.exit(1 if main() else 0)
