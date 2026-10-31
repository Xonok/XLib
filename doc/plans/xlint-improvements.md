# xlint improvements

Plan for the work asked of the secretary on 2026-10-31: improve `tools/xlint/`
so it covers more languages, reports a leading blank line, stops rescanning
everything on every change, and can dump its output to a file. Work proceeds in
chunks; one chunk per session, then `/new` and "continue improving xlint".

Status legend: **done** / **in progress** / **planned**.

## Chunk 1 — Leading blank line (standard, language-agnostic) — done 2026-10-31

Added `check_leading_blank(lines)` returning `(1, "empty line at start of file")`
when the first line is blank, wired into the `.py`, `.md`, `.js/.ts` and
`.html` branches of `check_file` under `--no-leading-blank` / `leading-blank`.
This is the first application of the "standard code shared across languages"
idea: one function, every language. Tests in `tools/xlint/test/test_xlint.py`
extended (`_every_check_on` flag list).

## Chunk 2 — Output to a file (`--output` / `-o`)

One-shot and watch mode. The file holds exactly what the terminal report holds;
when there are no issues it is **empty (size 0)**. Watch mode rewrites it on
every redraw, and truncates it to empty on a clean pass — never leaves stale
content behind. Needs care: atomic write (write to temp, rename) so a reader
never sees a half-written file; and in watch mode the write must follow the
same redraw ordering as the screen. Acceptance: `xlint . -o /tmp/out.txt`;
`test -s /tmp/out.txt` is false iff clean.

## Chunk 3 — Watch-mode rescan audit

Does xlint rescan everything when something changes? Partially yes:
`_repo_report(rules, list(snapshot))` re-runs every checkout's repo rules over
*all* files in scope on any dirty redraw, and the poll watcher re-stamps every
file. Built-in `check_file` runs only on changed files. Plan: make repo rules
incremental where a rule's `paths` selection allows it (re-run only on the
files whose content changed, plus a full pass on rule reload), and document the
cases where a full pass is genuinely required (rules that compare files).

## Chunk 4 — Module split

`tools/xlint/xlint.py` is ~2200 lines in one file. Split into a package:
`tools/xlint/__init__.py` (or keep entry), `_checks.py` (language-agnostic
standard checks), `_python.py`, `_markdown.py`, `_js.py`, `_html.py` (exists),
`_c.py`, `_watch.py`, `_io.py` (exclusions, ignore rules), `_repo_rules.py`,
`_cli.py`. Keep `tools/xlint/xlint.py` as the CLI entry that imports from the
package so existing callers (`xlint <paths>`, tests importing `tools.xlint.xlint`)
keep working. Tests must still pass without edits beyond import paths.

## Chunk 5 — Language rule wrapper

Introduce a per-language rule wrapper: each language declares a list of checks
(some language-specific, most calling shared standard functions such as
`check_leading_blank`, `check_trailing_blank`, `check_final_newline`,
`check_trailing_whitespace`, `check_double_blank`). `check_file` becomes a
dispatcher that selects the wrapper by suffix and runs its checks, applying
disabled flags. This is what makes "add a new language" a data change rather
than a code change.

## Chunk 6 — C support

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
