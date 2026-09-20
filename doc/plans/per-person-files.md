# Per-Person Operational Files

## Goal

Make the per-project master files (`STATUS.md`, `PLAN.md`, `TASKS.md`) *tracked but
personal*: the owner's version stays in git with full history safety, and anyone
else who pulls the repo gets their own version instead of inheriting the owner's.

## Current State

- `STATUS.md` is a plain tracked file at each repo root (`XLib/STATUS.md`,
	`/storage/Agents/STATUS.md`). Convention-only: **nothing in tool code**
	(agent-coord.py, taskview, marduk, skynet) hardcodes these paths; the rule
	lives in AGENTS.md ("one master status file per project") and agent role notes.
- Claim paths in agent-coord.py are pure `os.path.abspath` — string-identity only.
	Two spellings of the same file ("STATUS.md" vs "personal/Xonok/STATUS.md")
	would be different claim keys.
- XLib: only `STATUS.md`; working tree clean. `/storage/Agents`: all three files,
	but the repo is mid-reorg (PLAN/STATUS/TASKS **staged for deletion**, AGENTS.md
	modified) — migration there is BLOCKED until the human lands or abandons that reorg.
- No `.gitattributes`, no git filters anywhere in use.

## Requirements (confirmed with human 2026-09-20)

1. **Option B** — per-person tracked files under `personal/`, root files become
	per-person local symlinks. No smudge/clean filters, no silent-discard semantics.
2. **Identity** — `git config user.name`, falling back to `$USER` (e.g. `Xonok`).
3. **Scope** — `STATUS.md`, `PLAN.md`, `TASKS.md` in every project that has them.
4. Plain git only; mechanism must generalize to any project (it lives in XLib tooling).

## Design

### 1. Directory layout

```
personal/<person>/STATUS.md   <- tracked, per-person, full git history
personal/<person>/PLAN.md     <- tracked (only in projects that have one)
personal/<person>/TASKS.md    <- tracked (only in projects that have one)
STATUS.md                     <- gitignored symlink -> personal/<person>/STATUS.md
PLAN.md                       <- gitignored symlink -> personal/<person>/PLAN.md
TASKS.md                      <- gitignored symlink -> personal/<person>/TASKS.md
```

- Symlink targets are repo-relative (`personal/<person>/<FILE>`), so they survive
	moves. Symlinks are per-machine working views: one machine shows one person's
	files at a time under the root names; switching person = re-run init.
- `.gitignore` gains `/STATUS.md`, `/PLAN.md`, `/TASKS.md` per project.
- Person id sanitized for path safety: alphanumeric + `-`/`_`, no slashes;
	`git config user.name` first, else `$USER`, else env override `--person`.

### 2. `agent-coord.py personal` subcommand

- `personal whoami` — print the person id (config → env → $USER).
- `personal path [FILE]` — print `personal/<person>/[FILE]` (agents use this to
	know the canonical claim/edit target).
- `personal init [--person NAME] [--seed current|template] [--files STATUS.md PLAN.md TASKS.md]`
	- person id resolved as above.
	- per file: if `personal/<person>/<FILE>` exists → skip silently (never
		overwrite another person's content).
	- elif root `<FILE>` exists as a tracked real file and `--seed current` →
		`git mv` it into `personal/<person>/` (history preserved via rename detection);
		this is the owner-migration path.
	- else → write a blank template (header + "empty" note).
	- create the root symlink; refuse loudly if a root real file exists that
		wasn't just moved.
	- append the `/FILE` ignore entry if missing.
	- print a summary; exit non-zero on any guard failure.

### 3. Claim canonicalization

Change `claim_paths()` in agent-coord.py from `os.path.abspath` to
`os.path.realpath`. Effect: claiming "STATUS.md" and "personal/Xonok/STATUS.md"
resolve to the same key, so the symlink can't be used to bypass mutual exclusion.
Convention still standardizes on the `personal/<person>/...` spelling for clarity.

Caveat (verify during implementation): realpath on a *dangling* symlink must not
behave differently on claim vs release (Python resolves the final component only
if the target exists; both spellings of the same file must still collide). The
safe property to test: claim A, release B, then claim A again → works; and
claim A while B is held → fails. Regression-test those two cases.

### 4. Documentation updates

- **AGENTS.md (XLib + Agents)** — replace "one master status file per project"
	paragraph: master files live at `personal/<person>/`; root `STATUS.md` is a
	per-person working symlink created by `agent-coord.py personal init`; claims
	use the `personal/<person>/...` path spelling.
- **Coordinator / secretary role notes** — same wording (claim/update the
	personal path).
- **Installer script** — add idempotent `personal init` (any seed; existing
	tracked persona files make it a no-op beyond symlinking) so fresh machines
	and fresh clones get root symlinks. Fresh clones: `./setup.sh` already runs.

## Migration

### XLib (blocked on nothing — tree clean)

```
mkdir -p personal/Xonok
git mv STATUS.md personal/Xonok/STATUS.md
ln -s personal/Xonok/STATUS.md STATUS.md
echo '/STATUS.md' >> .gitignore
```

or equivalent single `personal init --seed current` once the subcommand exists.

### /storage/Agents (BLOCKED)

Human has PLAN/STATUS/TASKS staged for deletion + AGENTS.md modified (in-flight
reorg). Do NOT touch until human decides: if the staged deletion is intentional,
the three files may drop from tracking entirely at root — in that case the
personal/ migration for Agents starts from untracked originals and the staged
deletion resolves first. Ask the human which.

## Risks / unknowns

- **Claim realpath change** is global behavior for everyone — small, but lands in
	agent-coord.py; keep it behind the same `claim_paths` helper so tests cover it.
- **Fresh clone without setup.sh**: root symlinks absent until `personal init` —
	mitigated by AGENTS.md instruction + installer step.
- **`git add .`** never stages root symlinks (ignored) — intended, but anyone
	expecting `git status` to show `STATUS.md` changes will see
	`personal/<person>/STATUS.md<` instead. Mental-model shift, documented above.
- **History** of the moved file: `git log --follow -- personal/Xonok/STATUS.md`
	should surface the pre-move commits (rename detection); confirm during migration.

## Tasks

1. agent-coord.py: `personal` subcommand + realpath claim canonicalization — `worker-mimo` (dispatch coding).
2. XLib migration: personal/Xonok/STATUS.md + symlink + .gitignore — same coding dispatch or direct (single-step).
3. AGENTS.md + role notes wording (XLib + Agents) — documenter/secretary — after migration lands.
4. Installer: idempotent `personal init` step.
5. Agents repo migration — deferred on human reorg decision.
6. Update personal STATUS.md with this plan + "Recently done" entry when landed.