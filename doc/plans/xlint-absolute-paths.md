# xlint: flag absolute system paths in tracked Markdown

Status: **planned** — epi `7HP67R2`. The rule in `AGENTS.md:66-68` exists as prose only; the check that would enforce it does not.

## Problem

- A tracked file is versioned *and* synced between machines, so an absolute path is wrong in the ordinary way (it means nothing on another machine) and in the git way (it records one machine's layout as if it were the project's).
- The designated home already exists: `.agents/machine-info.md` is git-ignored *precisely* so it can hold machine-specific facts. That makes this a layering rule with a known landing place, not a matter of taste.
- 20 occurrences across 6 tracked files were cleaned by hand before this was filed; the rule has no mechanical check, so it kept slipping.

## Decision (human, 2026-09-27)

The rule reads in `AGENTS.md:66-68`:

> A tracked file is versioned *and* synced between machines, so it must not carry one machine's layout. Name a path relative to its repo, or point at the Agents workspace's `.agents/machine-info.md`, which is gitignored precisely so it can hold machine-specific locations. The exceptions are files whose subject *is* a location — a setup walkthrough's `scp` example, a plan about another host — a path quoted as evidence, and `personal/<person>/HISTORY.md`, which is per-person and exempt. xlint ticket `7HP67R2` will flag the rest.

## Requirements

### Core check

- Applies to `.md` files only (same `.md` branch as the space-indent check).
- Flag a path-like token that starts with:
	- `/storage/`
	- `/home/<user>/` (where `<user>` is any username)
	- `/root/`
	- `~/`
- Report at file:line with message: "absolute system path in tracked file — use a repo-relative path or point at `.agents/machine-info.md`"

### Exemptions (must all be handled)

1. **Git-ignored files** — `.agents/machine-info.md` itself and anything git-ignored. The destination is not a violation. Detection must be "is this file tracked" (`git ls-files`), not a path-prefix allowlist.

2. **`AGENTS.md` setup walkthrough** — `ln -s /path/to/XLib/tools …` and `scp -r /storage/Agents/ …` examples. The machine path is the *content* there. This is a single known file; match by path.

3. **Plans describing another machine's layout** — e.g., `plans/remote-opencode-lxc.md` with `/root/...` paths on the LXC host. Naming them is the document's subject. Match by path prefix `plans/` (or a curated list).

4. **Paths quoted as evidence** — a model-benchmark row quoting `/home/user/project/relative/path.py` as proof of a harness defect. The path describes no real location. This is the hardest exemption: the check cannot be "contains a slash-heavy token", it has to judge whether the path is *about* something or *about where something is*.

	**Approach:** Exempt lines that look like a quote/citation — lines starting with `> `, or inside a fenced code block that is clearly an example (heuristic: the fence info string suggests example, or the content is indented as a block quote). For the first pass, exempt fenced code blocks entirely (reuse `_fence_exempt`) and block-quote lines. The evidence case in the ticket is a fenced block.

5. **`personal/<person>/HISTORY.md`** — per-person and exempt per `AGENTS.md`. Match by path prefix.

### Scope guard

- The check applies ONLY to the `.md` branch of `check_file()`.
- It runs AFTER the existing exemptions (`_frontmatter_exempt`, `_fence_exempt`) so it can consume them — a path inside a fence or frontmatter is not flagged.
- `.py` checks are completely unchanged.

## Implementation

- Single file: `tools/xlint/xlint.py` (~800 lines). Claim via `agent-coord.py` before editing.
- Suggested shape:
	- Add `check_absolute_paths(lines, exempt_lines, path)` — a per-line token check that skips `exempt_lines` (union of frontmatter, fence, block-quote lines).
	- In the `.md` branch of `check_file()`, compute `exempt = _frontmatter_exempt(text_lines) | _fence_exempt(text_lines) | _blockquote_exempt(text_lines)` and pass to the new check.
	- Add `_blockquote_exempt(lines)` helper: line numbers where the line starts with `> ` (after optional leading whitespace).
	- Use `subprocess.run(["git", "ls-files", "--", path])` to test if a file is tracked; skip the entire check for untracked files.
	- Add a path-based allowlist for the known exemptions: `AGENTS.md`, `plans/`, `personal/*/HISTORY.md`.

- No version bump: `tools/` tools are not versioned libraries.

- Watch mode reuses `check_file()` per change — inherits the fix automatically.

## Verification

1. Create a scratch `.md` with `/storage/foo` → flagged.
2. Same content inside a fenced block → not flagged.
3. Same content in a block quote (`> /storage/foo`) → not flagged.
4. `AGENTS.md` with `ln -s /path/to/XLib/tools` → not flagged (path allowlist).
5. `plans/remote-opencode-lxc.md` with `/root/...` → not flagged (path allowlist).
6. `.agents/machine-info.md` (git-ignored) with `/storage/...` → not flagged (git ls-files returns nothing).
7. `personal/Xonok/HISTORY.md` with `/storage/...` → not flagged (path allowlist).
8. Regression: `python3 tools/xlint/xlint.py .` in XLib → 0 violations on tracked files.

## Optional follow-up (needs human sign-off)

The evidence exemption (item 4) is heuristic. If false positives appear, refine to a marker (e.g., a comment `<!-- xlint:allow-path -->` on the line) rather than guessing intent.

## References

- `AGENTS.md:66-68` — the rule text.
- `doc/plans/xlint-frontmatter-fence-skip.md` — the pattern this follows (same branch, same exemption structure).
- `GBNEWPS` — the implemented frontmatter/fence rule.
- `PMRBFR3` — final-newline for `.md`, same branch.
