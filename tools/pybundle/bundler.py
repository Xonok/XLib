import argparse,ast,os,sys

try:
	from .bundler_impl import (Context as _Context, Mod as _Mod, _analyze,
		_line_offsets, _merge_imports, _read_text, _rewrite, _tokenize_text,
		_topo)
except ImportError:
	from bundler_impl import (Context as _Context, Mod as _Mod, _analyze,
		_line_offsets, _merge_imports, _read_text, _rewrite, _tokenize_text,
		_topo)

def bundle(entry):
	"""Bundle `entry` (a file path) into one self-contained source string."""
	ctx = _Context(os.path.dirname(os.path.abspath(entry)) or ".")
	m = _Mod("", entry)
	m.rel = os.path.basename(entry)
	m.text = _read_text(entry)
	m.line_offsets = _line_offsets(m.text)
	m.tokens = _tokenize_text(m.text)
	m.tree = ast.parse(m.text)
	ctx.mods[""] = m
	ctx.entry = m
	_analyze(ctx, m)
	order = _topo(ctx)
	premerged = []
	for mm in [m] + order:
		for strip, ext in mm.imports_at.values():
			if strip:
				for line in ext:
					if line not in premerged:
						premerged.append(line)
	parts = []
	if premerged:
		parts.append("\n".join(_merge_imports(premerged)))
	first_body = True
	for mm in order:
		body = _rewrite(ctx, mm)
		if body.strip() == "":
			continue
		if first_body and premerged:
			body = body.lstrip("\n")
			first_body = False
		parts.append("############   from file: %s   ############\n\n%s" % (mm.rel, body.rstrip("\n")))
	entry_body = _rewrite(ctx, m)
	if entry_body.strip() == "":
		entry_body = m.text
	if first_body and premerged:
		entry_body = entry_body.lstrip("\n")
	parts.append(entry_body.rstrip("\n"))
	if ctx.warnings:
		print("pybundle warnings:", file=sys.stderr)
		for w in ctx.warnings:
			print("  " + w, file=sys.stderr)
	return "\n".join(parts) + "\n"

def main():
	ap = argparse.ArgumentParser(description="Bundle a python project into a single file.")
	ap.add_argument("entry", help="entry script")
	ap.add_argument("-o", dest="out", help="write output to file")
	args = ap.parse_args()
	result = bundle(args.entry)
	if args.out:
		with open(args.out, "w") as f:
			f.write(result)
	else:
		sys.stdout.write(result)

if __name__ == "__main__":
	main()
