#!/usr/bin/env python3
"""Measure a corpus of model-written explanations against the codebase they describe.

**What this measures.** A set of documents, one per model, all answering the same
prompt about the same repository. For each document it reports:

- **size** — words, lines, and how much of the answer sits under the deep dive;
- **structure** — whether the answer has the general-situation and deep-dive parts the
  prompt asked for, and how much internal structure the deep dive carries;
- **grounding** — whether the file paths the answer cites actually exist, checked
  against the real tree;
- **vocabulary** — whether the answer has a passage that defines the codebase's own
  terms, and how many term-definition bullets it carries.

**What it does not measure.** Readability, correctness and whether an explanation is
good are judgements, and a script that pretended to make them would be a second
opinion wearing a measurement's clothes. The path check is a fact — the file is there
or it is not — and the rest is structure, which is countable. A human reads the answers
and decides what they are worth; this puts numbers beside that reading.

**The prompt's own requirements** are given as arguments rather than assumed, because
the whole point is to measure one prompt's answers against *that* prompt:

    --general-word    a word that marks the general-situation part   (repeatable)
    --deep-word       a word that marks the deep-dive part            (repeatable)
    --glossary-word   a word that marks a passage defining terms      (repeatable)

    --vocabulary      a JSON file holding those three word lists, so that a corpus can
                      carry its own vocabulary instead of a reader having to copy a long
                      command line out of a README and get it subtly wrong

**Paths are arguments**, never hard-coded: the documents live wherever the caller put
them, the repository is wherever it is, and a sibling checkout is named explicitly.

Usage:

    python3 review_explanations.py --answers DIR --repo DIR --out FILE \\
        --general-word overview --deep-word "deep dive" --glossary-word glossary
"""
import argparse,json,os,re

# A file path the answer claims exists. The directories are the ones a codebase
# explanation reaches for, plus a bare module name with an extension.
PATH_RE = re.compile(r"\b((?:server|defs|client|tools|web|scripts|src|lib|pkg)/"
	r"[A-Za-z0-9_./-]+\.[A-Za-z0-9]+|[A-Za-z0-9_]+/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)")
BARE_RE = re.compile(r"\b([A-Za-z0-9_]+\.(?:py|json|js|ts|html|css|md|go|rs|java|rb))\b")
# A section label: a markdown heading, or a bare uppercase line. Both forms occur in
# model-written answers, and a checker that knows only the first reports a real
# section as missing — which is worst for the shortest answer, the one most likely
# to be the one under scrutiny.
LABEL_RE = re.compile(r"(?im)^(?:#{1,4}\s+(?P<md>.+)|"
	r"(?P<bare>[A-Z][A-Z0-9 ,.:/&'()\-]{3,70}))$")
NUMBERED_LABEL_RE = re.compile(r"(?im)^\d\.\s+(?P<title>[A-Z][^\n]{2,70})$")
# Structural marks inside a section: headings, numbered steps, table rows, bullets.
STRUCTURE_RE = re.compile(r"(?im)^\s*(#{2,6}\s|step\s+\d|\d+\.\s|\||[-*+]\s)")
# A bullet that defines a term: a bolded or quoted term, then prose.
TERM_BULLET_RE = re.compile(r"(?im)^\s*[*+-]\s+(?:\*\*[^*]{2,40}\*\*|`[^`]{2,40}`)\s*:?\s+\S")

def read_vocabulary(path: str) -> dict:
	"""The prompt's own vocabulary, as a JSON file.

	`{"general": [...], "deep": [...], "glossary": [...]}` — the three lists, each a list
	of lowercase words. A missing list is an empty list.

	Why a file: the words are DATA about one prompt, and a corpus that keeps them in a
	README's command line will drift from its own measurements the first time the
	command is edited and the output is not. A corpus that carries the vocabulary beside
	the answers cannot drift that way, and the reproduction becomes one short command.
	"""
	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)
	if not isinstance(data, dict):
		raise ValueError(f"{path}: the vocabulary must be a JSON object with the three "
			"word lists, not a list")
	out = {}
	for key in ("general","deep","glossary"):
		words = data.get(key) or []
		if not isinstance(words, list):
			raise ValueError(f"{path}: {key!r} must be a list of words")
		out[key] = [str(w).lower() for w in words]
	return out

def read_text(path: str) -> str:
	with open(path, encoding="utf-8", errors="replace") as fh:
		return fh.read()

def labels(text: str) -> list[tuple[int,str]]:
	"""Every section label in the text, as (offset, label).

	A bare line counts only when it looks like a title — short, entirely uppercase,
	no trailing sentence — because a wrapped line of prose is also mostly capitals.
	A numbered line counts only when it carries a title, because `2. Load definitions.`
	is a list item and not a heading.
	"""
	out = []
	for m in LABEL_RE.finditer(text):
		label = (m.group("md") or m.group("bare") or "").strip()
		if m.group("bare") and (label.endswith((".", "!", "?")) or len(label.split()) > 9):
			continue
		out.append((m.start(), label))
	for m in NUMBERED_LABEL_RE.finditer(text):
		out.append((m.start(), m.group("title").strip()))
	return sorted(out)

def find_split(text: str, general_words: list[str], deep_words: list[str]) -> tuple[int|None,int|None]:
	"""Where the general part ends and the deep dive begins.

	The general part is the first label matching a general word; the deep dive is the
	first label **after** it matching a deep word. Either may be absent, and that is
	worth recording rather than guessing at.
	"""
	marks = labels(text)
	general_at = None
	for off, label in marks:
		if any(w in label.lower() for w in general_words):
			general_at = off
			break
	deep_at = None
	for off, label in marks:
		if general_at is not None and off <= general_at:
			continue
		if any(w in label.lower() for w in deep_words):
			deep_at = off
			break
	return general_at, deep_at

def repo_files(roots: list[str]) -> set[str]:
	"""Every file under the given roots, as a path relative to its root."""
	out = set()
	for root in roots:
		if not os.path.isdir(root):
			continue
		for base, dirs, files in os.walk(root):
			dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
			for name in files:
				out.add(os.path.relpath(os.path.join(base, name), root))
	return out

def by_basename(paths: set[str]) -> set[str]:
	out = set()
	for p in paths:
		out.add(p.rsplit("/", 1)[-1])
	return out

def check_paths(text: str, roots: list[str], known: set[str], runtime: set[str]) -> tuple[set[str],set[str]]:
	"""Which cited paths exist, and which do not.

	A cited path can be written several ways and all are legitimate: relative to a
	repository root, relative to a package inside it, or as a bare module name. So a
	path resolves if it exists under **any** root, if its basename exists anywhere, or
	if the caller declared it runtime-written. A checker that called those false would
	report every answer as dishonest.
	"""
	all_files = repo_files(roots)
	names = by_basename(all_files) | by_basename(known)
	cited = set()
	for m in PATH_RE.findall(text):
		cited.add(m if isinstance(m, str) else m[0])
	for m in BARE_RE.findall(text):
		cited.add(m)
	resolved, missing = set(), set()
	for c in cited:
		c = c.strip(".,;:()[]'\"")
		if not c:
			continue
		if c in all_files or c in known or c in runtime:
			resolved.add(c)
			continue
		if any(os.path.join(root, c) for root in roots if os.path.isdir(root)):
			resolved.add(c)
			continue
		base = c.rsplit("/", 1)[-1]
		if base in names:
			resolved.add(c)
			continue
		# A schematic path: a placeholder where a name goes. The shape is real even
		# though the name is not.
		if "..." in c or base.startswith("x."):
			resolved.add(c)
			continue
		# A dotted reference to a function rather than a file.
		if "/" in c and "." in base[:-3]:
			resolved.add(c)
			continue
		missing.add(c)
	return resolved, missing

def measure(path: str, roots: list[str], known: set[str], runtime: set[str], words_cfg: dict) -> dict:
	"""One document's measurements.

	`words_cfg` carries the prompt's own vocabulary: `general`, `deep` and `glossary`,
	each a list of lowercase words.
	"""
	text = read_text(path)
	words = len(text.split())
	general_at, deep_at = find_split(text, words_cfg["general"], words_cfg["deep"])
	deep = text[deep_at:] if deep_at is not None else ""
	general = text[:deep_at] if deep_at is not None else text
	resolved, missing = check_paths(text, roots, known, runtime)
	names = [lbl.lower() for _, lbl in labels(text)]
	glossary = [lbl for lbl in names if any(w in lbl for w in words_cfg["glossary"])]
	return {
		"file": os.path.basename(path),
		"words": words,
		"lines": len(text.splitlines()),
		"has_general": general_at is not None,
		"has_deep": deep_at is not None,
		"general_words": len(general.split()),
		"deep_words": len(deep.split()),
		"deep_share": round(len(deep.split()) / words, 3) if words else 0.0,
		"deep_structure_marks": len(STRUCTURE_RE.findall(deep)),
		"cited_n": len(resolved) + len(missing),
		"resolved_n": len(resolved),
		"missing_n": len(missing),
		"missing": sorted(missing),
		"glossary_sections": glossary,
		"term_bullets": len(TERM_BULLET_RE.findall(text)),
	}

def main() -> None:
	p = argparse.ArgumentParser(description="Measure model-written explanations of a codebase")
	p.add_argument("--answers",required=True,help="directory of documents, one per model")
	p.add_argument("--repo",action="append",required=True,
		help="repository the answers describe; repeatable for a sibling checkout")
	p.add_argument("--known-path",action="append",default=[],
		help="a path that exists though it is not in the tree; repeatable")
	p.add_argument("--runtime-path",action="append",default=[],
		help="a path the code writes at runtime, absent from the tree; repeatable")
	p.add_argument("--out",required=True,help="where to write the measurements as JSON")
	p.add_argument("--general-word",action="append",default=[],
		help="a word marking the general-situation part; repeatable")
	p.add_argument("--deep-word",action="append",default=[],
		help="a word marking the deep-dive part; repeatable")
	p.add_argument("--glossary-word",action="append",default=[],
		help="a word marking a passage that defines terms; repeatable")
	p.add_argument("--exclude",action="append",default=[],
		help="a document name to leave out; repeatable")
	p.add_argument("--vocabulary",
		help="a JSON file with the general/deep/glossary word lists; the words given on "
			"the command line are added to these, not substituted for them")
	args = p.parse_args()
	names = sorted(n for n in os.listdir(args.answers)
		if n.endswith(".md") and n not in set(args.exclude))
	known = set(args.known_path)
	runtime = set(args.runtime_path)
	words_cfg = {"general": [], "deep": [], "glossary": []}
	if args.vocabulary:
		from_file = read_vocabulary(args.vocabulary)
		for key in words_cfg:
			words_cfg[key].extend(from_file[key])
	for key,flag in (("general","general_word"),("deep","deep_word"),("glossary","glossary_word")):
		words_cfg[key].extend(w.lower() for w in getattr(args,flag))
	rows = []
	for name in names:
		rows.append(measure(os.path.join(args.answers, name), args.repo, known, runtime, words_cfg))
	rows.sort(key=lambda r: r["words"], reverse=True)
	words = sorted(r["words"] for r in rows)
	summary = {
		"n_documents": len(rows),
		"median_words": words[len(words) // 2] if words else 0,
		"total_missing_cited_paths": sum(r["missing_n"] for r in rows),
		"rows": rows,
	}
	os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
	with open(args.out, "w") as fh:
		json.dump(summary, fh, indent=1)
	print(f"{'document':44s} {'words':>6s} {'deepW':>6s} {'deep%':>6s} {'marks':>6s} "
		"{'cited':>6s} {'miss':>5s} {'gloss':>6s} {'terms+':>7s}")
	for r in rows:
		print(f"{r['file']:44s} {r['words']:6d} {r['deep_words']:6d} {r['deep_share']:6.0%} "
			f"{r['deep_structure_marks']:6d} {r['cited_n']:6d} {r['missing_n']:5d} "
			f"{len(r['glossary_sections']):6d} {r['term_bullets']:7d}")
		if r["missing"]:
			print(f"    not found: {', '.join(r['missing'][:8])}")
	print(f"\n{summary['n_documents']} documents, median {summary['median_words']} words, "
		f"{summary['total_missing_cited_paths']} cited path(s) not found")
	print(f"wrote {args.out}")

if __name__ == "__main__":
	main()
