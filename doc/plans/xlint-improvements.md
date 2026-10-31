# xlint improvements

Plan for the work asked of the secretary on 2026-10-31: improve `tools/xlint/`
so it covers more languages, reports a leading blank line, stops rescanning
everything on every change, and can dump its output to a file. Work proceeds in
chunks; one chunk per session, then `/new` and "continue improving xlint".

**Workflow (ruling 2026-10-31):** xlint changes land directly on `master`,
without a branch, worktree, or review gate — the same standing exception
Marduk has. xlint is a style tool, so its changes are treated as safe by
default; review follows the commit rather than gating it.

Status legend: **done** / **in progress** / **planned**.

## Chunk 1 — Leading blank line (standard, language-agnostic) — done 2026-10-31

Added `check_leading_blank(lines)` returning `(1, "empty line at start of file")`
when the first line is blank, wired into the `.py`, `.md`, `.js/.ts` and
`.html` branches of `check_file` under `--no-leading-blank` / `leading-blank`.
This is the first application of the "standard code shared across languages"
idea: one function, every language. Tests in `tools/xlint/test/test_xlint.py`
extended (`_every_check_on` flag list).

## Chunk 2 — Output to a file (`--output` / `-o`) — done 2026-10-31

One-shot and watch mode. The file holds exactly what the terminal report holds;
when there are no issues it is **empty (size 0)**. Watch mode rewrites it on
every redraw, and truncates it to empty on a clean pass — never leaves stale
content behind. Needs care: atomic write (write to temp, rename) so a reader
never sees a half-written file; and in watch mode the write must follow the
same redraw ordering as the screen. Acceptance: `xlint . -o /tmp/out.txt`;
`test -s /tmp/out.txt` is false iff clean.

## Chunk 3 — Watch-mode rescan audit — done 2026-10-31

The built-in `check_file` already runs only on changed files. Repo rules now
skip individual rules whose selected files did not change, reusing cached
findings filtered to the files still in scope; a rule that touches a changed
file re-runs over its full selected set so cross-file rules still see every
file. A full pass runs on rule reload and in one-shot mode, and clears the
cache. Findings for deleted files are dropped even when no rule re-runs.
Rules that compare files cannot be safely narrowed to changed files alone, so
they re-run over their full selected set whenever any of their files changes.

Does xlint rescan everything when something changes? Partially yes:
`_repo_report(rules, list(snapshot))` re-runs every checkout's repo rules over
*all* files in scope on any dirty redraw, and the poll watcher re-stamps every
file. Built-in `check_file` runs only on changed files. Plan: make repo rules
incremental where a rule's `paths` selection allows it (re-run only on the
files whose content changed, plus a full pass on rule reload), and document the
cases where a full pass is genuinely required (rules that compare files).

## Chunk 4 — Module split — done 2026-10-31

`tools/xlint/xlint.py` (~2300 lines) split into a package: `tools/xlint/_io.py`
(exclusions, ignore rules, suffixes, tracked-file check), `_repo_rules.py`,
`_checks.py` (standard checks plus the `check_file` dispatcher), `_markdown.py`,
`_python.py`, `_js.py`, `_c.py`, `_watch.py`, `_cli.py`, with `_html.py`
already in place. `tools/xlint/xlint.py` is now a thin entry that re-exports
the module names (so `tools.xlint.xlint` and the CLI keep working); internal
imports fall back from package-relative to top-level so the file still runs as a
script. `__all__` on every module keeps the underscore names re-exported.
All 134 xlint tests pass and `xlint tools/xlint` is clean.
`tools/xlint/__init__.py` (or keep entry), `_checks.py` (language-agnostic
standard checks), `_python.py`, `_markdown.py`, `_js.py`, `_html.py` (exists),
`_c.py`, `_watch.py`, `_io.py` (exclusions, ignore rules), `_repo_rules.py`,
`_cli.py`. Keep `tools/xlint/xlint.py` as the CLI entry that imports from the
package so existing callers (`xlint <paths>`, tests importing `tools.xlint.xlint`)
keep working. Tests must still pass without edits beyond import paths.

## Chunk 5 — Language rule wrapper — done 2026-10-31

Implemented in `tools/xlint/_checks.py`: a `_Check` descriptor (attr, name,
rule, produce) plus per-language check lists (`_py_checks`, `_md_checks`,
`_js_checks`, `_html_checks`, `_c_checks`) and a `_SUFFIX_TO_LANGUAGE` map.
`check_file` is now a dispatcher: it picks the language by suffix, runs each
check unless its flag or canonical name is disabled, and applies the
tracked-only gating for absolute-paths. Adding a language is now a data change
(a new check list and suffix mapping) rather than editing the dispatcher.
All 113 xlint tests pass and `xlint tools/xlint` is clean.

## Chunk 6 — C support — done 2026-10-31

New suffixes `.c`, `.h` (and maybe `.cpp`/`.hpp`? decide). Rules: leading
blank, trailing whitespace, double blank, trailing blank, final newline,
space indent (tabs). No import or double-space rule initially (C has no
equivalent worth enforcing here). Needs a `--no-c-*` flag family or reuse of
the generic flags; prefer generic flags (`--no-trailing`, etc.) where the check
is shared, plus a C-specific disable name `c`? Decide in chunk. Also add C to
`_ALL_SUFFIXES` and to the parser description and docstrings.

## Chunk 7 — Epiq / ticket hygiene

No open epiq ticket currently covers this work (checked 2026-10-31: searched
all Todo/In-progress/Done titles for "xlint", "leading", "rescan", "output
file", "C support"). If the human wants tracking, file one ticket per chunk
on the XLib board rather than one umbrella ticket.

## Notes / decisions to settle with the human

- Message wording for the leading-blank check ("empty line at start of file")
	is new and has no spec; reviewer pass 2 has nothing to check it against.
- Whether C uses generic or C-specific disable flags.
- Whether `.cpp`/`.hpp` are in scope or only C.
- Whether the module split should preserve the single-file entry for backward
	compatibility with `tools/hooks/pre-commit` and `release.py`.
