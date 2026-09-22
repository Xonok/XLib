# xlint: skip YAML frontmatter and fenced code blocks in .md files

Status: spec written 2026-09-22, implementation NOT started.
Owner: any agent with coding duty (programmer/mechanic). Secretary does NOT implement (human decision).

## Problem

- opencode's agent/command/skill definitions are `.md` files — a markdown body
	wrapped in a YAML frontmatter header. YAML forbids tab indentation, so the
	header must use spaces.
- xlint's `.md` rule is a single check: every line matching `^ +\S` is
	reported as "indented with spaces". It has no markdown awareness — it flags
	every space-indented line, including YAML frontmatter.
- Concrete case (2026-09-22): `secretary.md` and `overseer.md` frontmatter was
	corrected from tabs to spaces. The tabs had caused silent YAML mis-parsing
	(`permission.task: deny` was silently dropped; overseer's frontmatter
	hard-failed and the agent stopped loading entirely). The correct
	space-indented frontmatter now trips xlint: 8 violations in those two
	files. 35 of 58 `.md` files under `/storage/Agents/.opencode/` carry
	frontmatter, so this pattern recurs across all of them.
- Additionally, the documented exception in AGENTS.md code style —
	"Markdown files: indentation uses tabs. Only exception: when tabs would
	break rendering (e.g., inside code blocks that require spaces)" — is not
	implemented anywhere. Fenced code blocks containing space-indented content
	(JSON/YAML examples in docs) are flagged today, contradicting the rule.

## Decision (human, 2026-09-22)

Implement both:
- **A — skip the YAML frontmatter block** in `.md` files for the space-indent
	check.
- **B — skip fenced code blocks** in `.md` files for the space-indent check.

Grunt details and verification below; they are part of the spec, not
suggestions.

## Requirements

### A — YAML frontmatter

- Applies to `.md` files only.
- A file whose FIRST line is exactly `---` has a frontmatter block: from line
	1 through the next line that is exactly `---` (inclusive). Lines inside
	that block are exempt from the space-indent check.
- Use the same frontmatter detection semantics as opencode
	(`packages/core/src/config/markdown.ts`): the regex
	`^---\r?\n([\s\S]*?)\r?\n---` anchored at file start. If the opening `---`
	exists but there is no closing `---`, the file has NO frontmatter — lint
	the whole file exactly as today.
- Mid-file `---` thematic breaks are never frontmatter.

### B — fenced code blocks

- Lines inside fenced code blocks are exempt from the space-indent check.
- Fence opener: a line at column 0 starting with ` ``` ` (3+ backticks) or
	`~~~` (3+ tildes), optionally followed by an info string. Closer: a line
	starting with the same character run, length at least that of the opener.
	Backticks and tildes do not mix (` ``` ` cannot close a `~~~` fence).
- The fence lines themselves are at column 0, so they are never flagged;
	an INDENTED fence line is a violation and stays one (house style forbids
	indented fences).
- Unclosed fence at EOF: everything after the opener is treated as code
	(human-readable behavior matches GFM: content renders as code to EOF).
- Indented (4-space) code blocks remain flagged — the convention is fenced
	blocks, and markdown indented code requires spaces by definition.

### Scope guard

- Frontmatter/fence exemptions apply ONLY to the `.md` branch of
	`check_file()` and ONLY to the space-indent check (the only check `.md`
	files receive today).
- `.py` checks are completely unchanged.
- The tab rule still applies to the markdown body of these files (prompt
	prose, lists, etc.).

## Implementation

- Single file: `tools/xlint/xlint.py` (~325 lines). Verified clean via
	`agent-coord.py check-clean` on 2026-09-22.
- Suggested shape (not prescribed):
	- In the `.md` branch of `check_file()`, replace the direct
		`check_space_indent(text_lines)` call with a variant that takes the
		exempt line ranges, or precompute an exempt-line mask.
	- One small helper for the leading-frontmatter spans; one small
		stateful pass for fences (track opener char + length, toggle on
		closer; open state to EOF as above).
- No version bump: `tools/` tools are not versioned libraries (the
	`VERSIONS.md` convention applies to `xlib/` libraries only).
- Watch mode reuses `check_file()` per change — inherits the fix
	automatically; no watcher changes.
- Process: claim `tools/xlint/xlint.py` before editing
	(`python3 tools/agent-coord.py claim tools/xlint/xlint.py`, run
	`check-clean` first), release when done.
- Code style: tabs for `.py` indentation, imports one-line comma-joined, no
	double blank lines, guard clauses, function definitions/calls on one line.
	See commit `05c6f54` ("Fix spaces with tabs in md files") for the
	indentation history.

## Verification (no test suite exists — manual, scratch files)

1. `python3 tools/xlint/xlint.py /storage/Agents/.opencode/agent/secretary.md
	/storage/Agents/.opencode/agent/overseer.md` → 0 violations
	(frontmatter lines exempt; body is tab-indented so it stays clean).
2. Regression: `python3 tools/xlint/xlint.py .` in XLib → still 0 violations.
3. Scratch `.md` cases (one file or several under `/tmp/opencode/`):
	- no frontmatter + a space-indented line → flagged (unchanged behavior).
	- frontmatter with space-indented keys → not flagged; a space-indented
		line in the body after the closing `---` → flagged.
	- first line `---` but no closing `---` → whole file linted.
	- fenced block (```, then JSON with spaces) → inside not flagged; a
		space-indented line after the closer → flagged.
	- `~~~` fence opened, closed by ` ``` ` → NOT closed (no mixing); verify
		the intended close by `~~~`.
	- unclosed fence → tail of file not flagged.
4. `.py` file with space indentation → still flagged (unchanged).

Report results (file paths + the observed violations) back with the change.

## Optional follow-up (needs human sign-off, do NOT do unprompted)

Update the AGENTS.md code-style exception wording so the documented rule
names YAML frontmatter explicitly, e.g.:
"Markdown files: indentation uses tabs. Exceptions: YAML frontmatter and
fenced code blocks, where spaces are required." Current text only mentions
"code blocks that require spaces" — it does not mention frontmatter, which is
a parsing requirement, not a rendering one. Flag it to the human; change only
with their approval.

## References

- opencode frontmatter parsing: `packages/core/src/config/markdown.ts`
	(gray-matter → js-yaml 3.x; frontmatter regex `^---\r?\n([\s\S]*?)\r?\n---`).
- The YAML-tab incident notes: `/storage/Agents/.agents/shared-notes.md`
	("YAML frontmatter in agent files: SPACES, never tabs, 2026-09-22").
- Affected files today: `/storage/Agents/.opencode/agent/secretary.md`,
	`/storage/Agents/.opencode/agent/overseer.md` (frontmatter already fixed).