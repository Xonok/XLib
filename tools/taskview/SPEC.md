<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

# taskview — project-specific views

> Written 2026-09-27 from the human's design decisions. The intent encoded here is
> the human's; the encoding is an AI interpretation. Decisions the human has not
> yet confirmed are marked **[CONFIRM]** in the Decisions section — the
> implementation follows the recommendation given there, so overruling one is a
> spec-and-test change made *before* code exists, which is the cheapest moment.

## Goal

The tmux task pane must show a person the tasks of the project they are sitting
in, not one global list sorted by due date across everything they are doing. Today
a single append-only CSV holds all 37 open tasks from every project, and the pane
headlines whichever is most overdue — so an XLib session currently presents an
mms-frontend task as "now", which is the concrete failure this change exists to
fix. Each project carries its own filter file so a taskview started inside it
shows local work; the filter lives in the project folder so it is versioned and
shareable, while the invocation decides which one applies so the tool is not tied
to one person's directory layout. One task keeps exactly one category, because a
system where everything must be classified pushes most tasks into a few common
categories while creating many categories for rare things — so the design gives
the major things their own category, lets everything unclassified fall into a
bucket list, and subdivides the large categories with tags rather than splitting
them.

## Data model

Unchanged. The CSV layout stays 8 columns and no column is added, moved, or
removed.

| Pos | Field | Meaning under this spec |
|---|---|---|
| 0 | `id` | unchanged |
| 1 | `status` | unchanged |
| 2 | `title` | unchanged |
| 3 | `due_ts` | unchanged |
| 4 | `chg_ts` | unchanged |
| 5 | `category` | **the project this task belongs to — exactly one, free text, may be empty** |
| 6 | `tags` | **subdivision within a category — no longer a membership axis** |
| 7 | `importance` | unchanged |

## Requirements

Numbered so tests can cite them. Each is one testable behaviour.

### Category and the bucket list

- **R1** A task's category is the value of column 5, a single free-text string. No
	task has more than one, and there is no multi-value syntax for it.
- **R2** An empty category is legal and is not an error state. A task with an
	empty category is called *uncategorised* and belongs to the **bucket list**.
- **R3** A filter with a non-empty `categories` list includes uncategorised tasks
	only if `include_bucket` is true.
- **R4** A filter with an empty `categories` list applies no category restriction.

### Filter file

- **R5** A filter file is a YAML file named `.taskview.yaml`, conventionally
	located in a project folder, and is read by an invocation that starts inside
	that folder (see Discovery).
- **R6** A filter file recognises exactly these keys:

	| Key | Type | Default | Meaning |
	|---|---|---|---|
	| `label` | string | the file's stem | human-readable name for the header |
	| `categories` | list of strings | `[]` | task categories to include; empty = all (R4) |
	| `tags` | list of strings | `[]` | tags to include; empty = no tag restriction |
	| `include_bucket` | bool | `false` | include uncategorised tasks (R3) |
	| `limits.upcoming` | int | `5` | max rows in the UPCOMING block |
	| `limits.queue_breakdown` | bool | `true` | show the due-horizon breakdown |

A complete filter file, as it looks on disk:

```
# <project>/.taskview.yaml — versioned with the project
# INDENT WITH SPACES. YAML forbids tabs for indentation, and the workspace's
# tab rule does not apply inside a YAML file. A tab anywhere in the
# indentation makes the whole file fail to load.
label: "XLib"
categories: ["XLib"]        # [] = unfiltered (the Agents global view)
tags: ["taskview"]          # optional, further subdivision
include_bucket: false
limits:
  upcoming: 5
  queue_breakdown: true
```

**This trap is real, not hypothetical.** The first `.taskview.yaml` written for
this change indented `limits:` with tabs, following the workspace rule, and
refused to load with `found character '\t' that cannot start any token`. The
test suite did not catch it, because its fixtures are written with spaces — a
passing suite does not validate anything the spec merely describes in prose.

- **R7** A key that is not in R6 is ignored, and a warning naming the key and the
	file is written to stderr. Unknown keys must not be fatal: the display runs in
	a tmux pane where a stack trace is invisible, and they must not be silent
	either, because a mistyped `upcoming` would otherwise change the display
	without trace.
- **R8** A malformed filter file (invalid YAML) is an error for that load:
	`load_filter` raises `FilterError`, and **the caller** — the render loop in
	`main()` — retains the filter it last loaded successfully, writes the parse
	error to stderr, and continues. `load_filter` itself is pure and holds no
	state. In `--watch` mode a later fix is picked up on the next change. The
	tool must not exit.

### Discovery

- **R9** The filter path is resolved in this order, first hit wins:
	1. `--filter PATH` if given → `source` = `explicit`.
	2. Otherwise, walk up from the current working directory; the first ancestor
	   directory containing a file named `.taskview.yaml` supplies it →
	   `source` = `discovered`.
	3. Otherwise, no filter applies (see R12) → `source` = `none`.
	4. `--no-filter` bypasses all of the above → `source` = `flag`.
- **R9a** `source` is part of the resolution result and must be carried through to
	the renderer. R24's three header states are distinguishable only by `source`:
	"no filter found" (`none`) and "explicitly unfiltered" (`flag`) both have no
	filter data, and the header must still tell them apart.
- **R10** The starting point for the walk is the **resolved** (symlink-free)
	working directory. This workspace reaches projects through symlinks
	(`/storage/Agents/tools` → XLib), and a physical-path walk would miss the
	filter in the directory the person actually chose to be in.
- **R11** The walk terminates at the filesystem root and is a plain filesystem
	walk: it must not invoke git, must not consult any per-user global
	configuration, and must not stop at `$HOME`. A filter in a parent directory
	deliberately captures its descendants — that is how a project folder scopes
	its subdirectories — and stopping at `$HOME` would make a stray
	`~/.taskview.yaml` silently capture every unrelated directory the person
	visits.
- **R12** When no filter is found, no category or tag restriction applies and the
	header states that no filter was found (R24). This is a *distinct* visible
	state from a filter that deliberately allows everything (R13).
- **R13** `--no-filter` skips discovery entirely and applies no filter, with its
	own distinct header state (R24). It is the escape hatch for wanting the global
	list while sitting inside a project folder.

### Selection order

- **R14** A task is selected by the first rule that applies:
	1. Its tags include `cancelled` or `archived` → **excluded**, unconditionally.
	2. Its category is not accepted by the active filter → **excluded**. Accepted
	   means: the filter's `categories` is empty (R4), or the task's category is
	   one of them, or the task is uncategorised and `include_bucket` is true.
	3. Its tags include `critical` or `emergency` → **included**, bypassing the
	   tag rule only.
	4. The filter's `tags` is non-empty and does not overlap the task's tags →
	   **excluded**.
	5. Otherwise → **included**.
- **R15** Rule 2 precedes rule 3 deliberately: `critical` and `emergency` are
	subdivision markers within a project, not global overrides. A `critical` task
	in another project must not appear in this project's pane, or the pane stops
	being a focus tool. The unfiltered view (R4) is where cross-project urgency is
	triaged.
- **R16** Rules 1 and 2 are unconditional exclusions; rules 3–5 decide inclusion
	among the rest. A task excluded by rule 1 or 2 is never counted as "filtered
	by this view" in the queue line (R23).

### Data location and test isolation

- **R17** The data directory is resolved as: `--data-dir PATH`, else
	`$TASKVIEW_DATA_DIR`, else `$XDG_DATA_HOME/taskview`, else
	`~/.local/share/taskview`. The CLI flag wins over the environment variable.
- **R18** `tasks.csv` defaults to `<data-dir>/tasks.csv` and `--csv PATH`
	overrides it independently.
- **R19** With `--data-dir` or `--csv` pointing outside the default location, the
	tool **must not create or modify anything under the default location**. The
	current auto-creation of `~/.local/share/taskview/filters/` and its copying of
	`default.yaml.example` into it is removed: under this design a project either
	has a filter or deliberately does not, and the tool must not plant one.
	*Testability:* because R17 resolves the default from `$XDG_DATA_HOME`, a test
	can redirect the "default" location into a temp directory by setting that
	variable, then assert nothing appears there — without any risk of the test
	writing to the real one.
- **R20** Terminal width is read at render time, not at import time, and
	`--width N` overrides it. A test must be able to obtain deterministic output
	without a tty.
- **R21** The selection and metrics logic is exposed as a pure function over
	(folded state, filter) with no I/O, so a future wide "all tasks" view can
	reuse it rather than reimplement the rules. That tool is **out of scope here**
	but this requirement exists so the next one does not have to change this.

### Watch mode

- **R22** In `--watch` the watch set is the CSV plus the **resolved** filter file,
	which is generally in a different directory from the CSV. inotify remains
	primary, 1-second polling the fallback, unchanged.
- **R23** If the resolved filter file is deleted or becomes unreadable while
	running, the render loop re-runs discovery, keeps displaying with whatever
	filter it can resolve (including none), writes a warning to stderr, and does
	not exit. *Verification:* this is the one requirement covered by inspection
	rather than by unit test — it is behaviour of the loop in `main()` that holds
	state across iterations, and the seam needed to test it would be more
	complicated than the behaviour. Everything it composes (`discover_filter`,
	`load_filter`, `build_view`) is tested directly.

### Display

- **R24** The header line renders one of three distinguishable states, chosen by
	the resolution `source` from R9a:
	- `explicit` or `discovered` (a filter was loaded):
	  `=== Tasks (<label>) ===`
	- `none` (discovery ran and found nothing):
	  `=== Tasks (no filter found — showing all) ===`
	- `flag` (`--no-filter` was given):
	  `=== Tasks (no filter) ===`

	The first and the other two must never render identically, so a pane showing
	everything because it is unconfigured cannot be mistaken for a pane showing
	everything on purpose.
- **R25** The queue line reports `(S shown, F filtered)` where S is the count of
	open tasks the filter selects and F is the count of open tasks it excludes.
	The invariant `S + F = (open tasks not excluded by R16 rule 1)` must hold
	exactly, so the two numbers are checkable against each other.
- **R26** Current-task selection, the UPCOMING list and its limit, PACE counts
	and the due-horizon breakdown keep their **existing algorithms verbatim** —
	same sorting (`due_ts` ascending, no-due last, `chg_ts` descending as
	tiebreaker), same day/week/month windows, same week/month/later horizon split.
	Only the input set changes: they are computed over the selected tasks
	(R14-R16) instead of the old tag-filtered set. "Unchanged" here means
	unchanged code, not "reimplemented to the same effect".
- **R26a** The header, the PACE block and the queue breakdown are not subject to
	R26: the header is specified by R24 and the queue's filtered count by R25.
- **R27** All rendering is pure: same (state, filter, width, source) in, same
	text out. No clock reads, no environment reads, no filesystem access inside
	the render path.

### Writer

- **R28** `taskupdate.py` must continue to accept `--category` and `--tags` on
	`add` and `update`. No writer interface is removed.
- **R29** Every write path (`add`, `update`, `done`, `cancel`) must write all 8
	columns, carrying forward the current values of every field it does not
	change. A completed task keeps its category and tags. This is a **regression
	guard**: the current code satisfies it, and the point is that adding a field
	later must not be possible to forget here.
- **R30** `taskupdate.py` resolves its CSV as `--csv PATH`, else
	`$TASKVIEW_CSV`, else `<data-dir>/tasks.csv` under R17's resolution. It
	must not write outside the resolved path.

### Removed

- **R31** `--context` and `$TASKVIEW_CONTEXT` are **removed**, not deprecated.
	Verified: nothing on this machine passes either — the only references are in
	the tool itself and in documentation. The legacy filter directory
	`~/.local/share/taskview/filters/` becomes unused; its five files are the
	human's data and are left on disk untouched, but no code reads them.
- **R32** The `*.yaml.example` files and `ensure_filter_dir()` are removed along
	with the auto-copy they exist for. XLib gets a committed `.taskview.yaml`; the
	Agents workspace gets one too (this change edits the Agents repo, which the
	human has authorised for this task).

### Reading old data

- **R33** A CSV row with fewer than 8 fields must not break reading. Missing
	trailing columns read as empty, so a legacy 5-column row has no category and
	is uncategorised.
- **R34** A row whose `chg_ts` is missing or unparseable, or whose `id` is not an
	integer, is skipped rather than aborting the read. Fold order is file order,
	last row per id wins.

### Resolving a task reference

Added 2026-10-01 (epiq `EY72YA9`), alongside the pane-side id prefix
(`X06YVNP`). A task id is only useful as a reference if something can resolve
it; before this, the only way to answer "what is #40?" was to open `tasks.csv`
and parse it by hand — the exact failure mode `AQQNPAN` describes.

- **R35** `taskupdate.py show <id>` prints that task's last row as id / status /
	title / due / due_ts / category / tags / importance. An empty optional field
	prints `(none)` rather than a blank label, so an empty column is visibly empty
	rather than absent.
- **R36** `show` on an id with no row exits **1** with a message naming the id. It
	must not exit 0 on a task it could not resolve.
- **R37** `show --field <name>` prints only that field's stored value and nothing
	else. `--field` names are the CSV column names (`id`, `status`, `title`,
	`due_ts`, `chg_ts`, `category`, `tags`, `importance`); the value printed is
	**what is stored**, not a formatted form, because the usual caller is an agent
	that wants to hand the value back to `update`. An unknown `--field` exits 1
	listing the valid names. The human-readable due form (`overdue 3d`, `today`)
	belongs to the full `show` view and to `list`, **not** to `--field due_ts` —
	a formatted string there could not be passed back to `--due`.
- **R38** `show` and `list` read through the same last-row-wins fold as `update`,
	so R33 and R34 apply to them: a legacy 5-column row resolves with empty
	category / tags / importance, and an id whose rows are mixed-width resolves to
	its last row however wide the earlier rows were.
- **R39** `taskupdate.py list` prints one line per task with the **id first**,
	ascending by id, so a task can be named without reading the CSV. `--status`
	and `--category` narrow the set. No matching task exits 1 with a message on
	stderr — an empty result is not a success, and a missing CSV exits 1 without a
	traceback.
- **R40** `show` and `list` are read-only: neither appends a row, creates the
	CSV, nor writes anywhere. R30's resolution order applies unchanged, and
	`--csv` / `$TASKVIEW_CSV` / `<data-dir>/tasks.csv` are honoured as they are by
	every write path.
- **R41** `list` is **not** the wide multi-axis view. That is `E5MH4S2`, a
	separate tool, and `list` must not grow into one: it prints the store, it does
	not analyse it. The one thing it adds over the raw CSV is the id in front.

### Showing the id

Added 2026-10-01 (epiq `X06YVNP`). The pane-side half of the pair specified in
R35-R41's preamble.

- **R42** The current-task line and every UPCOMING line render the task's id as a
	`#<id> ` prefix before the title. An id is the natural handle for a task, and
	until now the pane could not produce one: a task could only be named by its
	title, and two titles sharing a first few words were indistinguishable. A
	truncated title is worse than no title, because the identifying part is
	exactly what the cut removes.
- **R43** The prefix comes out of the **title's** budget, not the line's, so a
	title that fit before the change is still fully shown after it. `task_label`
	receives the line budget and subtracts the prefix width itself; a test asserts
	the title part equals `truncate(title, budget - len(prefix))`, so "the id was
	added and the title is now shorter" cannot pass.
- **R44** `truncate` never returns more than `width` characters, for any `width`
	including zero and negative. Before this it returned `text[:max(0, width-3)] +
	"..."`, which is three characters wide at `width == 0` — so a caller that
	subtracts a prefix from its budget could not rely on the line fitting.
	`task_label` depends on this guarantee, so the two requirements are one change.
- **R45** When the budget cannot hold the id and a title, the **title is dropped**
	and the id is truncated alone: a pane wraps badly long before a task becomes
	unnamed, and an id with no title is still a resolvable reference. For the same
	reason, when the remaining width cannot hold both a label and a due date, the
	UPCOMING line drops the due rather than overflowing.
- **R46** No rendered **task** line may exceed the render width, at any width, for
	either the current-task line or an UPCOMING line. Verified across widths 0-89
	with a fixture whose ids and titles are long enough to force every branch. This
	does not cover R24's header or the PACE / QUEUE blocks: those are not task
	lines and their widths are unchanged by this work.

## Decisions

Numbered, each with what was rejected.

1. **Exactly one category per task; uncategorised is legal.** Chosen because
	most tasks belong to a few common categories while most categories exist for
	rare things, and because forcing a wrong answer is worse than admitting there
	isn't one. *Rejected:* multi-valued categories (would let a task dodge the
	decision); making category mandatory (would fill the column with guesses, and
	a guessed category hides the task from every view).
2. **Category = what the work is about, not which repo you are sitting in.**
	Settles the two live ambiguities: a task planned from the Agents workspace
	about an mms-frontend change is an mms-frontend task; an XLib tool change is
	an XLib task even if its plan document lives in Agents. *Rejected:* category =
	current workspace (would move a task every time the person changed where they
	were sitting).
3. **Reuse the `category` column; add no column.** It is already single-valued,
	so the whole design is a vocabulary plus a cleanup of the 9 open tasks that use
	it. *Rejected:* a new `project` column (the SPEC's own "reschema support in
	CSV" is listed as unbuilt, and there is nothing a 9th column would carry).
4. **`.taskview.yaml` in the project folder, discovered from the working
	directory.** The human's reasoning: the file should be shareable and
	versioned with the project, but taskview is not user-scoped, so hardcoding a
	path into one person's data directory would break other users — the
	invocation picks the file instead. *Rejected:* `git rev-parse --show-toplevel`
	(a subprocess, and it fails outside a repository, so the tool would behave
	differently in a plain folder); a fixed per-user filter directory (breaks the
	sharing goal); one filter per *user* rather than per project.
5. **Walk to the filesystem root, no git, no `$HOME` stop.** *Rejected:* stopping
	at `$HOME` (one stray `~/.taskview.yaml` would then capture every unrelated
	directory the person visits — the failure mode is invisible).
6. **Symlinks resolved before walking.** *Rejected:* physical path (this
	workspace reaches XLib through `/storage/Agents/tools`, and the person
	chooses the directory, so the logical one is what they meant).
7. **No filter found → show everything, but say so in the header.** *Rejected:*
	erroring (in a tmux pane the message scrolls away and the pane looks broken);
	showing only the bucket list (magic, and it would look like data loss);
	silently showing everything (indistinguishable from a deliberate unfiltered
	view — the exact confusion this change must not introduce).
8. **Category filtering precedes `always_show`.** The tags `critical` and
	`emergency` bypass the tag rule but not the category rule. *Rejected (the
	existing behaviour):* letting them bypass everything — that behaviour predates
	categories, and carrying it over would let any critical task from any project
	headline every pane, which is the failure being fixed. **[CONFIRM]** — this
	reverses current behaviour, so the human should agree it is intended.
9. **Unknown filter keys warn; malformed YAML keeps the last good filter.** See
	R7, R8. *Rejected:* fatal on unknown key (kills a pane); silent ignore (a
	typo changes the display invisibly).
10. **Remove `--context` outright.** The human accepts breaking changes and
	nothing uses the flag. *Rejected:* a deprecation window (it would keep the
	tag-as-membership model alive in the one place it must not survive).
11. **Remove the filter auto-creation and the `*.yaml.example` files.** See R19,
	R32. *Rejected:* keeping a global "default" filter file, since a global
	default is indistinguishable from a project that has no opinion.
12. **`include_bucket`, default false.** *Rejected:* always including the bucket
	(it would put 28 unclassified tasks into every pane, which is the noise this
	change removes) and never offering it (a project pane cannot triage what has
	no category yet, so the labelling pass would have nowhere to show its work).
13. **The wide "all tasks, by priority" view is a separate spec and tool.** The
	human's own framing: all-tasks needs a wider perspective than a narrow pane
	provides, and the pane is good for focus. R21 exists only so that tool can
	reuse the selection rules. **[CONFIRM]** — if the human wants it in this
	change, say so before implementation starts.
14. **The CSV stays the single authority.** epiq boards, `TASKS.md` and
	`STATUS.md` are derivatives of it. Reducing the manual upkeep is real work
	with complications — those files also carry narrative the CSV cannot hold —
	and is deliberately **not** in this spec.
15. **The 28 uncategorised open tasks were not backfilled by this change.**
	They stay in the bucket list until the human labels them, which is a judgement
	about their own work. No backfill is part of this change. **Superseded in fact
	2026-09-27**: the labelling pass has since been done by the human's ruling
	(Decisions 18–20) and the bucket is empty. The decision stands as a statement
	about what the *change* did, not about the current state of the data.
16. **`Maintenance` is a category in its own right** (human delegated this
	decision, 2026-09-27). *Rejected:* making host upkeep a tag repeated inside
	every project category. The reasoning: the work is about the machine, not
	about any project, and it recurs indefinitely. As a tag it would be
	duplicated across every category, each project pane would carry maintenance
	noise it does not own, and "show me everything the machine needs" would have
	no single home — only a cross-project tag query in the unfiltered view. As a
	category it has one obvious home and the unfiltered view still finds it.
	*Honest tension, recorded rather than hidden:* `Maintenance` is a category
	with **no repository behind it**, so no `.taskview.yaml` can scope to it. In
	practice the human reaches it through the unfiltered view in the Agents
	workspace. That is acceptable precisely because the unfiltered view exists
	for cross-project triage, and a pseudo-project called "the machine" would be
	inventing a folder to justify a filter.
17. **Category names are the human's short names, not repository names.**
	`Traveller`, not `Space-Traveller` (human, 2026-09-27). The categories name
	*what the work is about*; a repository is one place that work happens, not its
	name. A category that must match a directory name drifts the moment a project
	is renamed, moved, or has work done from another folder — `Traveller` was
	already correct in the data and would have been "fixed" into
	`Space-Traveller` by anyone assuming the two must agree. *Rejected:* deriving
	category names from git roots, which couples the taxonomy to the filesystem.
18. **Category granularity is set by the tracker, not by how many tasks a group
	has** (human, 2026-09-27). The unit is the set of tasks that would share one
	tracker. Worked example, the human's: `note_viewer` (a library for
	mms-frontend), `mms` (the backend) and `mms-frontend` itself are **one**
	category — `work` — separated by the tags `note-viewer`, `mms-server`,
	`mms-frontend`, not three categories. Symmetrically, hobby programming is
	`XLib` (libraries shared by all of them), `Traveller` (a major project using
	XLib), and a bucket for the rest, until another project becomes major enough
	to warrant its own tracker. *This overrides the reasoning earlier in this
	spec*, which proposed subdividing the largest categories by tags: a category
	is **not** split by tags merely because it has accumulated many tasks. Tag
	subdivision earns its place by distinguishing members of one tracker (which
	repository, which project), not by keeping a count down. `Maintenance` (9 open)
	and `Personal Development` (3) are therefore deliberately left unsplit.
19. **The category vocabulary is `TASKS.md`'s section structure, adopted into the
	CSV** (human, 2026-09-27). The labelling pass found the vocabulary was already
	written: every one of the 28 uncategorised tasks already had a home in a
	`TASKS.md` section. The CSV's `category` column had been an ad-hoc subset never
	derived from it, so `TASKS.md` and `tasks.csv` were two taxonomies presenting
	as one list — which contradicts the decision that the CSV is the single
	authority and the others are derivatives. *Rejected:* inventing a fresh
	life-area axis for the CSV, which would have guaranteed the two files never
	agree. Consequence: a category name that appears in `TASKS.md` is the correct
	spelling, and renaming a section there is a change to the vocabulary.
20. **The column had been carrying three different axes simultaneously** (found
	during the labelling, 2026-09-27). Repository (`XLib`, `Agents`), life area
	(`Maintenance`, `personal`) and activity (`research`, `ai-docs`) were all in
	`category`. The activity values are the defect: they name what a task is being
	done *for*, not what it is about (Decision 17), and nothing in the toolchain
	rejects a new value, so the vocabulary was widening by accretion — one task at
	a time, per session, invisible until someone counted. Tracked as epiq
	`SNXBR23`; those tasks are left unchanged because a live session owns that work.

## Category vocabulary, as applied 2026-09-27

Eleven values, all of them either a project that warrants its own tracker or a
`TASKS.md` life area. A bucket is no longer needed: every open task is
categorised. Counts are open tasks as at 2026-09-27, and move as work does —
`XLib` shows 3 because #56 closed the same day.

| Category | Open | What it is |
|---|---|---|
| `Maintenance` | 12 | the machine and self-hosted infrastructure (Decision 16) |
| `Hobby` | 8 | the bucket for hobby projects without their own tracker |
| `work` | 3 | employment; repos separated by tag (Decision 18) |
| `XLib` | 3 | the shared library tooling |
| `Agents` | 3 | the agent workspace restructure |
| `Personal Development` | 3 | learning and skills |
| `Traveller` | 2 | Space-Traveller (Decision 17) |
| `Business / Career` | 2 | marketing, networking, gamedev community |
| `research`, `ai-docs`, `personal` | 5 | **off-vocabulary, pending** — epiq `SNXBR23` |

Only `XLib` has a project `.taskview.yaml`; `Agents` holds the unfiltered one.
The rest have no repository behind them and are reachable only through the
unfiltered view — the same accepted tension as `Maintenance` (Decision 16).
`Hobby` is the one name chosen by the secretary rather than taken from
`TASKS.md`; the human has not confirmed it. Within `work`, the tags are
`note-viewer`, `mms-frontend` and `career`; within `Hobby` and `Maintenance`
they are the project or subsystem name.

## What the human will notice, and should not be surprised by

Recorded here so a change in daily experience is not read as a bug.

- A project pane suddenly shows only that project's tasks. Tasks appearing in it
	yesterday are not lost — they are in the Agents unfiltered view.
- Every open task now carries a category (labelling pass, 2026-09-27), so a
	project pane showing two tasks is the real count, not a filtering failure. Most
	categories have no repository behind them and are reachable only from the
	unfiltered view — that is the accepted consequence of `Maintenance` (Decision
	16) generalised, not a bug. `Hobby` is deliberately one large bucket (Decision
	18): its members are separated by tag, and a project earns its own category
	only when it needs its own tracker.
- `critical` and `emergency` no longer leak across projects (Decision 8).
- Starting the tool outside any project shows everything, with a header that
	says so.

## Open, for the human

**Closed 2026-09-27** — recorded here so the resolutions are not lost with the
conversation:

- ~~**Decision 8** — reversing `always_show` precedence.~~ **Ruled: the way it is
	implemented stands.** `critical` and `emergency` no longer leak across
	projects; they bypass the tag rule only.
- ~~**The category vocabulary.**~~ **Ruled:** `Maintenance` is a category of its
	own (Decision 16), and `Traveller` is the spelling, not `Space-Traveller`
	(Decision 17).
- ~~**Decision 13** — wide view in this change or its own spec.~~ **Ruled: its own
	spec, not built here.** Tracked as epiq ticket `E5MH4S2` on the XLib board.
- ~~**The labelling pass** — 28 open tasks, and whose judgement it is.~~
	**Done 2026-09-27.** All 28 labelled, plus #58 relabelled `Agents` → `work`.
	Bucket list empty. Vocabulary recorded in Decisions 18–20.
- ~~**The remaining category names.**~~ **Ruled and applied** — see the
	vocabulary table above. Two names remain unconfirmed: `Hobby` (invented by the
	secretary; `Projects` was the alternative) and whether `Mistlands` should be
	its own category rather than a tag inside `Hobby`.

**Still open:**

- **`/storage/Agents/.taskview.yaml` documents three categories that do not
	exist** (`mms-frontend`, `Mistlands`, `MaFE` are in zero rows) and omits three
	that do (`research`, `ai-docs`, `personal`). The human has left the file alone
	for now. Tracked as epiq `QKRW2Z0`.
- ~~**Task ids are not shown in the pane.**~~ **Ruled and implemented
	2026-10-01** — specified as a pair and landed together: the resolver side is
	R35-R41 above (`EY72YA9`), the pane side is R42-R46 (`X06YVNP`). Paired because
	an id in the pane that nothing can resolve is a worse gap than no id at all:
	it invites the reader to ask "what is #40?" and then go read the CSV by hand.
	Raised by the human 2026-09-27.

## Interfaces

The technical encoding the tests import. Names and signatures are part of this
contract; behaviour is in the requirements above. Pure functions must be
importable without side effects (R20, R27).

`taskview.py`:

```python
def resolve_data_dir(explicit: Path | None, environ: dict) -> Path
	# R17. explicit --data-dir, else $TASKVIEW_DATA_DIR, else
	# $XDG_DATA_HOME/taskview, else ~/.local/share/taskview.

def resolve_csv(data_dir: Path, explicit: Path | None) -> Path
	# R18. --csv wins, else <data-dir>/tasks.csv.

def load_filter(path) -> dict
	# keys: label, categories (set), tags (set), include_bucket (bool),
	#       limits{upcoming, queue_breakdown}, _path
	# raises FilterError on unreadable or malformed YAML (R8). Pure, no state.

def discover_filter(start: Path) -> Path | None
	# R9 rule 2 and R11: start.resolve(), walk to filesystem root,
	# first .taskview.yaml wins, None if none.

def resolve_filter(cwd: Path, explicit: Path | None, no_filter: bool
		) -> tuple[Path | None, dict | None, str]
	# R9, R9a, R13. Returns (path, filter_data, source) where source is one of
	# "explicit", "discovered", "none", "flag". filter_data is None unless
	# source is "explicit" or "discovered".

def select_tasks(state: dict, filter_data: dict | None) -> dict
	# R14-R16. Pure. id -> task, for tasks of ANY status that pass. A None
	# filter passes everything except R16 rule 1.

def compute_metrics(state: dict, selected: dict, filter_data: dict | None) -> dict
	# R25, R26. Pure. Keys: done_day, done_week, done_month, active,
	# this_week, this_month, later, open_tasks, shown, filtered_total.
	# `selected` is every status that passed the filter (as the old `filtered`
	# argument was); `shown` and `filtered_total` count OPEN tasks only.

def build_view(selected: dict, metrics: dict, filter_data: dict | None, width: int, source: str) -> str
	# R24, R26, R26a, R27. Pure.

def watch_targets(csv_path: Path, filter_path: Path | None) -> list[Path]
	# R22. The CSV plus the resolved filter file if there is one, de-duplicated.
	# Both may live in different directories.

def truncate(text: str, width: int) -> str
	# R44. Shorten to fit width, marked with an ellipsis. Never returns more than
	# max(0, width) characters, so a caller may subtract a prefix from its budget
	# and rely on the line still fitting.

def task_label(task: dict, budget: int) -> str
	# R42, R43, R45. "#<id> " then the title truncated into what is left of
	# budget. A budget too small for the id returns the truncated id alone.

def read_csv(path: Path) -> dict
	# R33, R34. Unchanged behaviour.
```

`taskupdate.py` keeps its CLI shape. `parse_due` and `read_last_id` are
unchanged; the resolution of the target CSV follows R30.

`taskupdate.py` additionally exposes:

```python
def read_task(path: Path, task_id: int) -> dict | None
	# R38. Last row for task_id as an 8-key dict, or None when there is no such
	# row. Short rows read as empty (R33). This is the reader `update`, `done` and
	# `cancel` use, so all four resolve a task the same way.

def read_all(path: Path) -> dict
	# R38, R39. Every task by id, last row per id winning. `read_task` is this
	# fold restricted to one id.

def fmt_due(ts: str | int) -> str
	# Human due wording, matching taskview's pane: "no due", "overdue Nd",
	# "today", "tomorrow", "Nd", else YYYY-MM-DD. An unparseable timestamp returns
	# "unparseable due (<value>)" rather than raising — a bad value in the store is
	# a display problem, not a reason to lose the whole row.
```

`FilterError` is a new exception type raised only by `load_filter`.

## Traceability

Every requirement above is cited by at least one test, and every test cites a
requirement. The test suite is written from this file, before any implementation
change.
