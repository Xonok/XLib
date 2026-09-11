# xaudit — project-specific lint tool

Status: decided — implementation pending

## What it does

xAudit checks XLib-specific structural rules that xlint (generic Python style)
doesn't cover. It lives in `tools/xaudit/` and is not a releasable library.

xAudit calls xlint internally, so one command shows both project and style
issues. xlint remains runnable standalone for style-only checks.

## Classification

xAudit classifies paths it's given:

- **Tool**: anything under `tools/` (e.g. `tools/xaudit/`, `tools/skynet.py`)
- **Library**: top-level `<name>/<name>.py` (e.g. `xcsv/xcsv.py`, `xtest/xtest.py`)
- **Other**: anything else — ignored by library/tool checks, only xlint runs

**Decided:** `xlint/` and `release/` move into `tools/`. `pybundle/` stays at
root (it's a dependency of the release tool, not a standalone tool).

### Blast radius of the move

Code that breaks or needs a path update:

| Where | What | Action needed |
|-------|------|---------------|
| `tools/tmux-xlib.sh:10` | runs `python3 xlint/xlint.py --watch .` | update path to `tools/xlint/xlint.py` |
| `release/release.py:4-7` | `ROOT = parents[1]`; `from pybundle import bundler` | after move, `parents[1]` is `tools/` — needs to resolve repo root still (parents[2] or walk up for the folder containing `pybundle/`) |
| `readme.md:29` | mentions `release/release.py` | update path |
| `pybundle/SPEC.md:136` | mentions `release/release.py` | update path |
| `plans/release-script.md` | multiple references | update path |
| `plans/reviewer-agent.md` | release exec commands | update path |
| `plans/skynet-second-tracker-spec.md:163` | tmux send-keys xlint path | update path |
| `plans/README.md:38`, `plans/testing.md:25` | doc references | update path |

Docs/reviews/audits referencing the old paths are historical records — no
change needed.

**Check before moving:** STATUS.md says release.py carries uncommitted WIP
(bundle-integration change, currently broken). The move carries that WIP
along; the human owns the move (it's a git change) and should decide whether
to commit first.

## Checks

### Phase 1 (initial implementation)

| # | Check | Scope | Pattern |
|---|-------|-------|---------|
| 1 | No `__init__.py` in library root | libs only | `<lib>/__init__.py` must not exist |
| 2 | VERSIONS.md exists | libs only | `<lib>/VERSIONS.md` must exist |
| 3 | No unversioned xlib imports | libs only | `from xlib import <name>` where `<name>` has no `_X_Y_Z` suffix |
| 4 | Library entry file = re-exports only | libs only | `<lib>/<lib>.py` must not contain `def `, `class `, or control flow (`if `, `for `, `while `) at top level. Allowed: `from ... import ... as ...`, assignments, docstrings |
| 5 | Tool entry file = has code | tools only | `tools/<name>/<name>.py` (or `.sh`, `.js`) must contain actual logic, not just imports |
| 6 | `._` prefix access | all `.py` files | Flag `._` that isn't `.__` (dunder exception). Warning. |

### Phase 2 (future)

| # | Check | Notes |
|---|-------|-------|
| 7 | `_`-prefixed names not imported cross-file | Needs import resolution across files. Lower priority — `._` check catches most cases. |

## Design

### CLI

Same shape as xlint:

```
python3 tools/xaudit/xaudit.py <paths...>    # one-shot
python3 tools/xaudit/xaudit.py --watch <paths...>  # watch mode
python3 tools/xaudit/xaudit.py --no-<check> <paths...>  # disable a check
```

Internally calls xlint on the same paths, merges output. Warnings, not errors
(exit 0 on issues, same as xlint).

### Output format

Same as xlint: `<path>:<line>: <message>`, sorted. xlint results are prefixed
or interleaved — the user sees one combined stream.

### Structure

```
tools/xaudit/
    xaudit.py    # entry point, CLI, orchestration
```

Single file. Checks are functions like xlint (`check_init_py`, `check_versions_md`,
etc.). No external dependencies beyond stdlib.

## Open questions

- What depends on the current `xlint/` path (scripts, tmux config, docs)?
  Answered above — see blast radius table.

**Decided:** xaudit owns the watch loop; in watch mode it calls xlint in
one-shot mode on every pass and merges both outputs. xlint is never run in
watch mode by xaudit (two watchers would fight over the terminal). The tmux
pane runs `xaudit --watch` which shows both project and style issues.
