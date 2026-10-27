"""Deterministic checker for the module move. Exit 0 = every reference is updated and the
project behaves as it did before the move.

The structural half is derived from the tree and `moves.json` rather than typed by hand: a
case per move ("the old module is gone", "the new module imports") and one aggregate scan
for any surviving reference to an old path. The behaviour cases exercise the project
through the new layout with expected values computed from their inputs.

Usage:
	python3 check.py          human-readable, exit 0/1
	python3 check.py --json   per-case results, for collateral-damage detection
"""

import ast,importlib,json,os,subprocess,sys,tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))

def _moves():
	with open(os.path.join(ROOT,"moves.json")) as f:
		return json.load(f)

def _python_files():
	for dirpath,dirnames,filenames in os.walk(ROOT):
		dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
		for name in sorted(filenames):
			if name.endswith(".py"):
				yield os.path.join(dirpath,name)

def _module_files():
	"""Every importable module under `stockroom/`, as module name -> path."""
	out = {}
	base = os.path.join(ROOT,"stockroom")
	for dirpath,dirnames,filenames in os.walk(base):
		dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
		for name in sorted(filenames):
			if not name.endswith(".py"):
				continue
			path = os.path.join(dirpath,name)
			parts = os.path.relpath(path,ROOT)[:-3].split(os.sep)
			if parts[-1] == "__init__":
				parts = parts[:-1]
			out[".".join(parts)] = path
	return out

def _hits(module,name):
	return module == name or module.startswith(name + ".")

def _stale(path,olds):
	"""Old module names referenced by the imports in one file, as `line: text` strings."""
	tree = ast.parse(open(path).read(),path)
	found = []
	for node in ast.walk(tree):
		if isinstance(node,ast.Import):
			for alias in node.names:
				if any(_hits(alias.name,old) for old in olds):
					found.append(f"{node.lineno}: import {alias.name}")
		elif isinstance(node,ast.ImportFrom) and not node.level:
			base = node.module or ""
			for alias in node.names:
				candidates = (base,base + "." + alias.name)
				if any(_hits(candidate,old) for old in olds for candidate in candidates):
					found.append(f"{node.lineno}: from {base} import {alias.name}")
					break
	return found

def _relative_imports(path):
	tree = ast.parse(open(path).read(),path)
	return [node.lineno for node in ast.walk(tree)
		if isinstance(node,ast.ImportFrom) and node.level]

def _import(name):
	return importlib.import_module(name)

def _import_all():
	"""Every module under `stockroom/`, imported by its new name. Returns the failures."""
	failures = []
	for name in sorted(_module_files()):
		try:
			importlib.import_module(name)
		except Exception as e:
			failures.append(f"{name}: {type(e).__name__}: {e}")
	return failures

def _run_tests():
	proc = subprocess.run([sys.executable,"run_tests.py"],cwd=ROOT,capture_output=True,
		text=True,timeout=120)
	return proc.returncode,(proc.stdout + proc.stderr).strip()

# Behaviour cases. Each one imports through the new layout, so an unreferenced stale
# import in any module it touches shows up here as an ImportError rather than as a reason
# the case is skipped.
def _units():
	u = _import("stockroom.core.units")
	return u.to_grams(2,"kg") == 2000 and u.from_grams(2500,"kg") == 2 \
		and u.to_millimetres(3,"cm") == 30

def _money():
	m = _import("stockroom.core.money")
	return m.pct(5,50) == 3 and m.format_cents(1234) == "12.34" \
		and m.format_cents(-5) == "-0.05"

def _paths():
	p = _import("stockroom.config.paths")
	return os.path.isfile(p.data_file("supplier-export.csv"))

def _settings():
	s = _import("stockroom.config.settings")
	return s.rates_file().endswith("rates.csv") and os.path.isfile(s.export_file())

def _items():
	i = _import("stockroom.items")
	item = i.StockItem("BOLT-M8","M8 bolt",2500,120)
	return item.mass_kg() == 2 and item.value_cents(3) == 360

def _problems():
	p = _import("stockroom.problems")
	return issubclass(p.UnknownSku,p.StockError)

def _orders():
	o = _import("stockroom.domain.orders")
	order = o.Order([(120,3),(80,2)])
	return order.subtotal_cents() == 520 and order.total_cents(20) == 624 \
		and order.shipping_weight_grams() == 5000

def _stock():
	s = _import("stockroom.domain.stock")
	i = _import("stockroom.items")
	book = s.Stock()
	book.add(i.StockItem("BOLT-M8","M8 bolt",2500,120),4)
	return book.value_cents() == 480 and book.mass_kg() == 10 and book.quantity("BOLT-M8") == 4

def _suppliers():
	s = _import("stockroom.domain.suppliers")
	return s.payable_cents(1000,"nord") == 950

def _shipping():
	s = _import("stockroom.domain.shipping")
	return s.shipping_cents(2500,10) == 495 + 240 + 30

def _formats():
	f = _import("stockroom.reporting.formats")
	return f.money_line("total",1234) == "total: 12.34"

def _daily():
	d = _import("stockroom.reporting.daily")
	o = _import("stockroom.domain.orders")
	i = _import("stockroom.items")
	s = _import("stockroom.domain.stock")
	book = s.Stock()
	book.add(i.StockItem("BOLT-M8","M8 bolt",2500,120),4)
	return d.daily_summary(book,[o.Order([(120,3)])]) == {
		"revenue":360,"tax":72,"stock_value":480,"units":3}

def _monthly():
	m = _import("stockroom.reporting.monthly")
	return m.month_totals([{"revenue":100},{"revenue":250}]) == {
		"revenue":350,"formatted":"3.50"}

def _csvio():
	c = _import("stockroom.io.csvio")
	p = _import("stockroom.config.paths")
	rows = c.read_items(p.data_file("supplier-export.csv"))
	book = c.stock_from(p.data_file("supplier-export.csv"))
	return len(rows) == 3 and sorted(book.items) == ["BOLT-M8","NUT-M8","WASHER-M8"]

def _jsonio():
	j = _import("stockroom.io.jsonio")
	i = _import("stockroom.items")
	with tempfile.TemporaryDirectory() as d:
		path = os.path.join(d,"items.json")
		j.export_items(path,[i.StockItem("BOLT-M8","M8 bolt",2500,120)])
		with open(path) as f:
			payload = json.load(f)
	return payload[0]["sku"] == "BOLT-M8" and payload[0]["mass_g"] == 2500

def _cli():
	c = _import("stockroom.cli")
	return c.main(["value"]) == "stock value: 0.00" and c.main(["orders"]) == "orders: 39.00"

# (account, guard, what it witnesses, function). A guard passes before the work and must
# still pass afterwards; the flags were marked by running `check.py` on the untouched tree,
# not by reasoning about it.
BEHAVIOUR = [
	("behaviour-units",True,"unit conversions are arithmetic only",_units),
	("behaviour-money",True,"half-up rounding and formatting",_money),
	("behaviour-paths",True,"the data directory resolves from config/",_paths),
	("behaviour-settings",False,"settings imports paths",_settings),
	("behaviour-items",False,"items imports units",_items),
	("behaviour-problems",True,"the exception hierarchy is unchanged",_problems),
	("behaviour-orders",False,"orders imports money and units",_orders),
	("behaviour-stock",False,"stock imports money, units and items",_stock),
	("behaviour-suppliers",False,"suppliers imports money",_suppliers),
	("behaviour-shipping",False,"shipping imports money and units",_shipping),
	("behaviour-formats",False,"formats imports money",_formats),
	("behaviour-daily",False,"daily imports money, orders and stock",_daily),
	("behaviour-monthly",False,"monthly imports daily and money",_monthly),
	("behaviour-csvio",False,"csvio imports stock",_csvio),
	("behaviour-jsonio",False,"jsonio imports items, which did not move",_jsonio),
	("behaviour-cli",False,"the command line runs through the new layout",_cli),
]

def _run(fn):
	try:
		value = fn()
	except Exception as e:
		return False,f"{type(e).__name__}: {e}"
	return bool(value),"ok" if value else "assertion failed"

def cases():
	moves = _moves()
	olds = [move["old"] for move in moves]
	out = []
	for move in moves:
		old,new = move["old"],move["new"]
		def old_absent(old=old):
			return old not in _module_files(),f"{old} is gone"
		out.append({"account":f"old-path-{old}-absent","guard":True,
			"witnesses":f"{old} must not exist under any name","run":old_absent})
		def new_imports(new=new):
			_import(new)
			return True,f"{new} imports"
		# Whether the module could be imported before the work: true only for the three whose
		# own dependencies did not move. Measured by running `check.py` on the untouched tree
		# (a module whose dependency chain reaches a stale import fails transitively, which is
		# why this is recorded rather than inferred from the module's own file).
		out.append({"account":f"moved-{new}-importable","guard":move["guard"],
			"witnesses":"the module is reachable at its new path","run":new_imports})
	def top_level(name):
		return name in _module_files(),f"{name} is at the top level"
	for name in ("stockroom.items","stockroom.problems"):
		out.append({"account":f"{name.rsplit('.',1)[1]}-at-top-level","guard":True,
			"witnesses":f"{name} did not move","run":lambda name=name: top_level(name)})
	def import_all():
		failures = _import_all()
		return not failures,"; ".join(failures[:8]) if failures else "every module imports"
	out.append({"account":"imports-stockroom","guard":False,
		"witnesses":"every module under stockroom/ imports by its new name","run":import_all})
	def stale_anywhere():
		found = []
		for path in _python_files():
			if os.path.basename(path) == "check.py":
				continue
			try:
				found.extend(f"{os.path.relpath(path,ROOT)}:{line}"
					for line in _stale(path,olds))
			except SyntaxError as e:
				found.append(f"{os.path.relpath(path,ROOT)}:{e.lineno}: syntax error: {e.msg}")
		return not found,"; ".join(found[:12]) if found else "no reference to an old module"
	out.append({"account":"no-stale-imports","guard":False,
		"witnesses":"no import anywhere names an old path","run":stale_anywhere})
	def relative_anywhere():
		found = []
		for path in _python_files():
			if os.path.basename(path) == "check.py":
				continue
			try:
				found.extend(f"{os.path.relpath(path,ROOT)}:{line}"
					for line in _relative_imports(path))
			except SyntaxError as e:
				found.append(f"{os.path.relpath(path,ROOT)}:{e.lineno}: syntax error: {e.msg}")
		return not found,"; ".join(found[:12]) if found else "absolute imports only"
	out.append({"account":"no-relative-imports","guard":True,
		"witnesses":"the tree stays on absolute imports","run":relative_anywhere})
	def tests_pass():
		code,output = _run_tests()
		return code == 0,output[-400:] if code else "run_tests.py passed"
	out.append({"account":"run-tests","guard":False,
		"witnesses":"the project's own tests pass","run":tests_pass})
	for account,guard,witnesses,fn in BEHAVIOUR:
		def behaviour(fn=fn):
			return _run(fn)
		out.append({"account":account,"guard":guard,"witnesses":witnesses,"run":behaviour})
	return out

def main():
	results = []
	for case in cases():
		try:
			passed,detail = case["run"]()
		except Exception as e:
			passed,detail = False,f"{type(e).__name__}: {e}"
		entry = {"account":case["account"],"passed":bool(passed),"guard":case["guard"],
			"witnesses":case["witnesses"],"detail":detail}
		results.append(entry)
	if "--json" in sys.argv:
		print(json.dumps({"cases":results,
			"passed":sum(r["passed"] for r in results),"n":len(results)},indent=2))
		return 0 if all(r["passed"] for r in results) else 1
	for r in results:
		if not r["passed"]:
			print("FAIL",f"{r['account']}: {r['detail']}  [{r['witnesses']}]")
	failed = [r for r in results if not r["passed"]]
	if failed:
		print(f"\n{len(failed)}/{len(results)} cases failing")
		return 1
	print(f"all {len(results)} cases pass")
	return 0

if __name__ == "__main__":
	sys.exit(main())
