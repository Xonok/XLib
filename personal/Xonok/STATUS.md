# XLib STATUS — master file

The current picture of this workspace: what exists, what is being worked on, what
is blocked, and what needs a decision. Present tense only — anything worth
reading in six weeks is in `HISTORY.md`. Details live behind the pointers at the
bottom; this file stays a summary.

## Convention (all agents)

- Update this file when you start or finish something, or when your progress
	estimate changes. One line per work item: what, who, % done, where to look.
- Claim `STATUS.md` before editing (`python3 tools/agent-coord.py claim
	STATUS.md`), release when done.
- Finished items are appended to `HISTORY.md`, not moved to a "Recently done"
	section here. The open list simply loses them. History is append-only:
	nothing is rewritten or removed without the human's sign-off.
- The % done number is **your own estimate of how done you think it is** — rough
	is fine, stale is not.
- Keep the Snapshot date current. It is the basis of the file, not a log.

## Snapshot

Basis: `master` at `ad47b60` (2026-10-17), **snapshot taken 2026-10-17**, **three
commits ahead of `origin/master` and unpushed** — the human authorised the commit, not
the push.

**The bundler is written, runs, and is committed (`ba063b5`). All 188 tests pass.**
This was done out of lane — implementation is programmer work and the secretary
agent does not write programs; the human overrode that on 2026-10-17 after being
told, and the record says so rather than quietly absorbing it. **806 lines across
five modules**, xlint clean, verified beyond the fixtures: a hand-built tree
bundles to a file that runs and prints the right values.

**Does python allow a relative import in the root? Yes — and this repo depends on
it.** D15's `RELATIVE_IMPORT_IN_ROOT` rested on *"which python does not allow"*,
and that holds for a module run as `__main__` and not for one imported as part of
a package. Checked both ways: `import pkg.mod` runs clean, `python pkg/mod.py`
raises `ImportError: attempted relative import with no known parent package`.
**`dev/xhttp/test/harness.py:7` puts `dev/` on `sys.path` so `from xhttp import
xhttp` works**, so the root file is always a package module here and
`from ._ import …` is legal — and it is the house idiom in xcsv, xhttp and xtest.
**RULED 2026-10-17: the rule is relaxed and the error retired** — `SPEC.md` D30,
and the blocker this paragraph opened is gone. The evidence that it was the only
blocker is in *Blocked* item (a): **`dev/xhttp` bundles with its root untouched and
its own 223-test suite runs against the bundle with the same 2 failures the source
has.** Taskview `#130`.

**Two of the 188 could not pass as written, and both were wrong; they are fixed.**
In `test_bundler_structure.py`, the placement test compared
`Path(value.__module__).name` against `"bundler_source.py"` — `__module__` is a
dotted module name, never a filename, so no import mechanism produced it. And the
tokenize test matched `^\s*import\s+tokenize\b`, which only a *single-name* import
satisfies while `doc/style/python.md:26` mandates comma-joined imports, so it
matched none of this repo's own imports. Both helpers fixed to match their intent,
on the human's authorisation having been told. A third fix is in
`test_bundler_imports.py`, whose `write` helper never created parent folders and
so killed its own fixture; the other five suites' helpers do.

**`release.py` still fails**, now with `AttributeError` rather than `ImportError`:
the spec has no `bundle(entry) -> str`, and the human chose "bridge separately",
so `1ZY2Q5Q` stays open past the landing, as task **#129**. **F21 was tolerated
rather than settled** — `imports` accepts a slash-spelled or a dot-spelled
modpath, because the loop hands it one and the test another.

**The working tree is still not clean, and what is in it is not pybundle's** —
modified `tools/marduk/_/sse_client.py`, `tools/marduk/_/state.py`,
`tools/marduk/marduk.py`, `tools/oc-agent` and `tools/skynet.py`, untracked
`tools/marduk/_/service.py`, `tools/marduk/_/session_watcher.py`, `tools/marduk/test/`
and `tools/skynet/CHANGES.md`. **Left alone deliberately**: not mine, not this task's,
and not mine to commit. The pass-3 material is
kept below for what it settled: 188 tests in six files plus
`doc/reviews/pybundle-tests-pass1-3.md`, committed as `de4f70b`. The pass-2 history is
kept below for what it settled: 138 tests in five files plus
`doc/reviews/pybundle-tests-pass1-2.md`, 9 files and 1102 insertions, with the four
rulings recorded in the commit body, including that **F13 was reversed** — which is
why 138 is not a stable number and 188 is the current one. xhttp arrived in
`dev/` from Space-Traveller on 2026-10-10; its root is clean — documentation,
`xhttp.py`, the internals in `_/`, the suite in `test/`, and `compare/` holding
the temporary RFC comparison material (`ba84849`). The suite is at **223 tests /
2 failures / 1 skipped**, unchanged by `95d700b`; see *In progress*. Its design
record lives at `dev/xhttp/SPEC.md`. **xlint reports clean over the
whole repo, and that is narrower than it reads** — it skips every directory named
`test`, so its violations are invisible to it (epi `AK633QC`).
**Nothing can be released at all right now**, for two independent reasons: the
dev-folder path fix landed in `c657694` (`1ZY2Q5Q`), but `release.py` imports
the bundler at module scope and **the bundler was deleted** in `5e87ae8`, so
the script now fails at *import* rather than at bundle time. Read Blocked before
trusting a release. **195 epiq
events were stranded on 2026-10-01, 13 of them issue creations**; the drain ran
on 2026-10-02 and `tools/epiq-pending.py` reports **1 event still stranded**
(a bare `create.contributor` carrying no ticket content), confirmed 2026-10-08.
**The merge queue is empty again.** Four tickets were approved by the human on
2026-10-08 and merged as a flat rebase sequence, no merge commits:
`AFVAWRX` (#26), `3EEXMRK` (#21), `FZDMC84` (#23), `4N5J1AS` (#25). Before them,
six merged on 2026-10-02 — `58MXTGY`, `EY72YA9`, `X06YVNP`, `CMGDFZF`, `0ZSB1DP`,
`PMRBFR3` — and twelve before that. `doc/development.md` is the canonical process
document — plan → spec → tests → implementation → review, each stage entered on
the human's call.

- **Technical explanations have a rule file.** `doc/style/prose.md` — cite
	identifiers, trace rather than summarize, mark inference, state what would
	falsify the answer. Landed as `KDX7KWJ` because ordinary AI prose reads fine
	but a technical one loses the chain and comes back as word salad; the rules
	make the explanation checkable against the artifact instead. Explanation work
	goes to a step-by-step reasoning model — the small workers narrate a
	conclusion rather than deriving one.

- Libraries: `dev/` holds xconf, xcsv, xprod, xschema, xtest. `xlib/` holds
	xconf `1_0_0`, xcsv `1_0_0`/`1_0_1`/`1_1_0`, xschema `1_0_0`, xtest `1_0_0`.
	xprod is unreleased.
- SPEC.md exists for xconf, xcsv, xschema, xtest and for the marduk, pybundle
	and taskview tools. `dev/xprod/` has only a README.md.
- Nothing under `.opencode/` is tracked: `.opencode/agent` is a gitignored
	symlink into the Agents workspace (the single canonical agent set), and
	`.opencode/opencode.jsonc` and `node_modules` are ignored too. There is no
	coordinator agent file — planning and assumption-auditing belong to the main
	model.
- Live coordination state: `python3 tools/agent-coord.py status` (claims) /
	`news` (changed rule files).
- **There are two epiq boards, one per repo, and 16 tickets moved between them
	on 2026-09-30.** The filing rule is that a ticket belongs on the board of the
	repo where its change lands, because that is the only board whose state
	branch can see the commit. See `AGENTS.md` under *Working on a ticket* for
	the rule and `58MXTGY` for the ref map.

## In progress

| Item | Who | Done | Where |
|------|-----|------|-------|
| **pybundle rewrite** | human (intent) / AI (spec) | **IMPLEMENTED 2026-10-17, out of lane on the human's override. 806 lines, five modules, 186 of 188 tests pass, xlint clean.** Uncommitted. See the Snapshot for the two test defects and the three un-ruled consequences. **Implementation landed; `release.py` did not, and neither did the review.** Pass 3's 188 tests were committed as `de4f70b`; the two failures are both in `test_bundler_structure.py` and both are unsatisfiable as written. Pass 1's 65 tests were superseded on 2026-10-15 by **138 tests in five files** — that is pass 2, committed as `247eaba`, since superseded again by pass 3's 188 — re-derived against `SPEC.md` after the pass-1 decisions (`03c0e75`) and after the human answered F13–F17. **Every decision they prompted has been ruled** — `S1G5037` and `F7KHKM8` both had their `human-input-needed` tags removed after the rulings. **`#127`'s spec half is done** (`5e4784a` + the spec commit below): a new
	*Decisions — 2026-10-15, after test pass 2* section, **268 insertions / 0
	deletions**, with the first 730 lines verified byte-identical so the
	append-only discipline of `03c0e75` holds. **D20** alias (reverses D9 and
	F13) · **D21** INDENT/DEDENT · **D22** `text`/`indent` plus the argv,
	empty-line and `pass` clauses · **D23** D14's fourth diagnostic, fully
	specified · **D24** collisions · **D25** the count is six. It opens by
	saying **read D20 first — it reverses D9 two hundred lines up**, because an
	implementer working top to bottom builds the withdrawn mechanism otherwise.
	**What remains is the reviewer's re-derivation**, and the spec now names the
	seven cases it must pin.
	**The re-derivation is done — pass 3, 2026-10-15, and it is uncommitted.** 176
	tests in five files, described in `doc/reviews/pybundle-tests-pass1-3.md`; a
	conformance audit on 2026-10-17 found **three tests that cannot pass against a
	conforming bundler** and all three are fixed: `test_out_dash_writes_the_bundle_to_stdout`
	asserted `helper__count` in a tree whose `setUp` had stopped importing `helper`
	(**committed in `247eaba`, so two review passes missed it**), and the two D23
	anchor tests gave the root no indentation at all, which made them contradict
	their own sibling `test_a_root_without_indentation_reports_nothing_when_the_files_agree`
	— no implementation satisfies both. A fourth, `test_a_comment_line_carries_no_indentation_of_its_own`,
	asserted the opposite of its own name and is renamed. **188 tests now, in six
	files**: the three coverage gaps are closed (R6.1's `tokenize` half, which no
	test asserted; `imports`'s entry count, which D8 and D16 fix but nothing pinned;
	and R5's "raises the same errors either way"), and the new `test_bundler_imports.py`
	is the file for the one function D12 names that no file tested directly.
	**All four still cannot run — there is no implementation.**
	**One ruling recorded: D26** — a mixed statement's non-local half is aliased too
	(`import helper, os` → `import os as sub__client__os`), which supersedes D8's
	`becomes import os`. Three tests already asserted it; no test changed.
	**The three blocking flaws are ruled and written in, 2026-10-17 — D27, D28,
	D29**, all appended, nothing above them edited. **F25**: a use of a
	name-imported name *is* rewritten, to the importing file's own prefixed name —
	the bullet saying "nothing rewrites the use" would have produced a bundle raising
	`NameError` that still passes a text-level test, and it contradicted D20's own
	verified table. **F26**: a plain local module import emits **no rebind** — its
	name is an alias for the callee's prefixed globals, because there is no module
	object to bind (D17) and aliasing would make python re-import the file. **F29**:
	the indentation report carries **the file's path, the first offending line's
	number, and that line's text**, the path written the way the start comments write
	it. F27, F28, F30, F31 and F21 remain open and none of them blocks.
	**188 tests now, in six files** — the two new ones pin the report's path and
	number, which F29's ruling made testable. **All committed as `de4f70b`**; the pass-3
	spec edits beyond these four decisions are still not written in, so the spec does
	not yet carry all of its own tests. | epiq `6MFX0Z1`, `YEBP3QB`, `S1G5037`, `F7KHKM8`, `R9H4PVD`, `EZAVYNM` |
| **xhttp** | human | **Moved in from Space-Traveller 2026-10-10**; `xlib_dev` load fixed (#116). **Suite: 223 tests, 2 failures, 0 errors, 1 skipped** as of `f83b050` — was 19 errors until the file-serving tests were corrected from tuple config to the dict shape `_/response.py` actually reads. The 2 remaining failures are **real defects**, not test noise: `_/websocket.py:send` does not validate message type, so `send(None)` and `send(<non-string>)` raise nothing (board `7Z7DE78`). Left red on purpose — `TESTING_RULES.md` forbids masking an implemented feature's failure. Root is now clean: docs, `xhttp.py`, `_/`, `test/`, and `compare/` for the temporary RFC comparison material (`ba84849`, #124), plus `REVIEW.md` and `TODO.md` (`0a0dcd8`, #118). `95d700b` relocated the 60s-timeout fix into `handshake()`; it does not regress it and closes none of `Z70VRAC`'s five faults. **Not yet validated against real code in Space-Traveller**, the human's stated condition for calling it done. **The root file now reflects the error classes (2026-10-17, uncommitted)** — nineteen `err_X = err.X` lines at `xhttp.py:62-80`, added so a caller of a *bundle* can still name them (see *Blocked* (a)). Bundled, they come out as `err_HTTPError = _err__HTTPError`; the suite still runs 223 with the same 2 failures. | `dev/xhttp/`, `dev/xhttp/SPEC.md` |
| **modelbench** | — | Under active work (commits 2026-09-28/29 replaced the results catalogue with `ledger.py`); two questions left | `tools/modelbench/`, taskview #61, #63 |
| **epiq boards** | secretary | XLib **33 open, all 33 in Todo — In progress and Done are both empty**, verified 2026-10-15; four of those are the pybundle spec tickets raised by test pass 2 (`S1G5037`, `F7KHKM8`, `R9H4PVD`, `EZAVYNM`). An empty In progress lane is a reading, not a fact about the work: the work is happening on a branch, which the lane does not track. The 2026-09-30 reshuffle put every ticket on the board of the repo its change lands in; this repo also carries a readonly `Closed` archive board | both boards |
| **xAudit tool** | — | Decided, not started | `doc/plans/xaudit.md` |
| **taskview periodic time refresh** | — | Planned only | `doc/plans/taskview-time-refresh.md` |

### Merging

The human's decision of 2026-09-30: every piece of work goes on its own
feature branch, one commit per ticket, ref-prefixed, and **nothing merges
before the human reviews it**. Agents move finished tickets to Done themselves;
after the human has approved a ticket an agent may merge it to master, delete
the branch, and close the ticket (epiq `H2NC2A2`).

**The queue is empty.** The 2026-10-02 run held six and merged them as a flat
rebase sequence, in dependency order and not in approval order: `58MXTGY` (the
filing rule, so it governs the rest), then `EY72YA9` before `X06YVNP` — the
pane-side id prefix was rebased onto the resolver-side commit, because `X06YVNP`'s
own ticket says an id in the pane that nothing can resolve is worse than no id —
then `CMGDFZF` and `0ZSB1DP`, which are independent, then `PMRBFR3` last so the
stricter `.md` rule landed on top of everything the other five wrote. A second
run on 2026-10-08 merged four more — `AFVAWRX`, `3EEXMRK`, `FZDMC84`, `4N5J1AS` —
all approved by the human that morning and all rebased first, because three of
the four rewrote `STATUS.md` from the same old base and conflicted with each
other; oldest basis went first so the newest reconciliation landed last. Every
commit subject opens with its ticket ref, which is what keeps the commit↔ticket
linking readable (why: `HISTORY.md` 2026-10-01, the `9R0H6SA` entry).

`gh` 2.102.0 is installed at `/usr/local/bin/gh` — official release binary, no
apt source added — and is authenticated against `Xonok` with `repo` scope. An
agent opens and merges pull requests; the human reviews. `epiq_issue_stats
<ref>` gives per-ticket size, self-churn and test lines — read it before the
diff.

**The subject format is `<REF> ` — ref, then a space.** `REF: ` does not link:
the matcher is `subject.toUpperCase().startsWith(ref + " ")`. All seven were
committed the git way first and read as zero commits; epiq's own skill never
states the separator. A rebase merge preserves it; a merge commit would bury
it under a refless subject.

### pybundle — the folder is documents only, and three of them disagree

**There is no bundler in the tree.** The five-phase implementation
(`bundler.py` + `bundler_impl.py`) and its seven fixtures were deleted on
2026-10-14 (`5e87ae8`, epiq `055TS78` closed by deletion). `tools/pybundle/`
now holds four documents and no code, and a reader arriving there sees **three
specifications with nothing marking which is current**:

- **`SPEC.md`** — the one the rewrite follows. Written by an AI, carries
	`<!-- spec-origin: ai -->`, derived from `DRAFT.md` with each decision
	cited back to a draft section.
- **`SPEC_old.md`** — the old `SPEC.md`, renamed. Describes the deleted
	5-phase `Context`-based bundler. It is a record, not a plan.
- **`SPEC_new.md`** — the human's earlier handwritten attempt, brought in from
	outside the repo in `79acddf`. Its own commit subject said "Needs more
	work", and `DRAFT.md` carries its intent forward. The rewrite does not
	follow it.

`DRAFT.md` is the human's intent and is the source of truth for what the
rewrite is for. The spec-input constraint — the output sink is anything
file-like — is written into `SPEC.md` as requirement R5 (epi `YEBP3QB`), which
it had been missing from every prior draft.

Also standing, from the abandoned single-pass attempt:

- The four `doc/reviews/pybundle-*.md` reviews approved files which were never
	in the tree (`pybundle.py`, `BUG_FIX_SPEC.md`, `VERSIONS.md`, three fixtures).
	They are the record of a real attempt, not a verdict on anything.
- `tools/pybundle/_/` is an empty directory left behind, and
	`tools/pybundle/test/` no longer is — it held the 65 tests committed in
	`608621e` and now holds **138 in five files, of which two files are untracked
	and three more are modified**; nothing from the pass-2 derivation is
	committed. Git does not track empty directories, so `_/` exists on disk and
	not in the repository.

## Blocked / needs attention

- **Work on a branch is not live until it merges.** Established by `HC1ZJK6`:
	the `worker-ling` → `worker-longcat` fix for `dispatch general` arrived as an
	uncommitted working-tree edit, and moving it onto a branch — which the
	workflow requires — took it out of the checkout, leaving the pin broken and
	`dispatch general` still answering "Upstream request failed". Now merged and
	verified live, but the shape of the problem is general: **anything repairing
	a running thing is unfixed for the whole review window**, which is correct
	for review and wrong for a fix. Worth deciding whether an infra repair may
	land ahead of review.
- **`.work/` is gitignored now, and the convention travels** — **fixed
	2026-10-01** as `b7211a2` (epiq `XRVB0W5`, PR #24, merged and closed). Both
	halves of the finding below are done: `.gitignore` carries `.work/`, so
	`git add .` no longer stages a worktree as an embedded-repo gitlink, and the
	rule itself moved from gitignored `.agents/shared-notes.md` into `AGENTS.md`
	next to the branch-per-ticket rule. **Corrected 2026-10-01**: when this was
	first written it read *`.work/` is not gitignored, and it holds two live
	worktrees* — true an hour earlier, and the reason the fix landed inside the
	same session rather than after it.
- **`VERSIONS.md` entries should cite the release's epiq ref where one exists**
	(human, 2026-10-01; epiq `NCPBQ3W`). **Libraries only** — no tool has a
	`VERSIONS.md`, by standing rule. Forward, not retrofit: no release commit has
	ever carried a ref, so all six existing entries stay as they are and the first
	entry that can cite one is the next release. Mechanizable — each released file
	has exactly one adding commit, so the ref is findable via
	`git log --diff-filter=A`, and the check should validate against **git rather
	than the board**, since the board is not durable.
- **`tools/release/release.py` cannot release anything — two independent breaks,
	one now fixed and one deeper.** The dev-folder path bug is **fixed and
	committed** (`c657694`, epiq `1ZY2Q5Q`): it resolved `ROOT / <library>`
	while the folders moved under `dev/` in `da1d163` (2026-09-17). **But the
	script still cannot release anything**, because it imports the bundler at
	module scope (`release.py:8`) and the bundler was deleted in `5e87ae8` — so
	it now fails at **import**, before reaching `bundler.bundle(...)` at line 74.
	Nothing releasable before either; what changed is that this break is no
	longer a one-tab fix and now waits on `6MFX0Z1`. **The documentation half of
	that ticket is now done** (`d908568`): `release.py:58` says
	`dev/<library>/<library>.py` and the README marks its bundler citation
	unavailable rather than leaving a reader to run it. Still unaddressed: the
	non-atomic write, `release()`'s return type and the tagging question. **And
	the consequence worth stating plainly** — the README's "never run this to
	check something" warning exists because a stray `release.py <library>`
	leaves a real file in `xlib/`, and its answer, inspect the bundler
	directly, no longer works. **There is currently no way to look at a bundle
	without writing one.** All six releases in `xlib/` predate the move and
	nothing tests the path.
- **The pybundle rewrite has code: the bundler is implemented and 186 of its 188
	tests pass.** Implementation is programmer work and the secretary does not do
	it; the human was told and overrode that, so the work happened here and the
	record says so. What that leaves behind is three things the human has not
	ruled on, and they are worth more than the green tests:
	**(a) RULED 2026-10-17: a relative import in the root is allowed, and
	`RELATIVE_IMPORT_IN_ROOT` is retired** (`SPEC.md` D30, taskview `#130`).
	D15's premise — *"which python does not allow"* — holds for `__main__` and
	not for a package module, and a library's root file is a package module.
	Measured, not argued: with the check removed and `dev/xhttp/xhttp.py`
	untouched, the library bundles to 552 lines and **its own suite runs 223
	tests against the bundle with the same 2 failures the source has**, plus a
	12-case live-socket smoke test with byte-identical wire responses. The
	refusal was the only blocker — `imports` had already resolved `from ._ import
	…` to six local targets. The source-side workaround does not exist:
	`from _ import helper,…` breaks `from xhttp import xhttp` with
	`ModuleNotFoundError: No module named '_'`, so this had to be a bundler
	decision. The human's reason for relaxing rather than narrowing it: *"Callers
	are not supposed to use those. That's part of why the root file of a library
	needs to reflect whatever internals matter."* **The cost of that is real and
	was accepted**: the internals stop being reachable as attributes of the
	bundle, so **a caller can no longer name the library's error classes** — the
	human answered that on the source side the same day, adding nineteen
	`err_X = err.X` lines to the root file, which the bundler passes through as
	`err_HTTPError = _err__HTTPError` (223 tests, same 2 failures, re-measured).
	**The implementation is not done**: two lines in `bundler.py`, the exception's
	four import sites, and four tests that pin the error. **A bundled library
	cannot be tested by its own suite** — `test_response.py:25` and
	`test_websocket.py` import internals and D17 means a bundle has no module
	objects — so running all 223 needed a shim package; the human's answer is
	*"we'll probably have to add an option to the bundler for making these shims
	automatically. Future work"*, filed as `#133`.
	**(b) The release path is still down**, one layer in: `release.py:8` imports
	fine now and `:74` calls `bundler.bundle()`, which the spec does not have.
	The human chose *"spec as written, bridge separately"* over adding it, so
	`1ZY2Q5Q` outlives the landing. **What now stands between `dev/xhttp` and a
	file in `xlib/`, measured 2026-10-17** — none of it is xhttp's own code, and
	all of it is cheap or already decided:
	1. **The guard above is still in the tree** (`#132`, epiq `NJ529TQ`) — the
		committed bundler refuses xhttp's root today.
	2. **The bundler has no `bundle(entry) -> str`** to call (`#129`, epiq
		`1ZY2Q5Q`); the bridge is unwritten by decision.
	3. **The bundle fails xlint, and the pre-commit hook runs xlint on staged
		`.py`, so it cannot be committed.** Three findings, all in the bundler's
		emission: `space after comma in import` and `aliased import on a shared
		line` from D20's alias form, and a **`double blank line`** where a removed
		import sat between two blanks — structural, so any normally-formatted
		library hits it. **The second cannot be fixed by rewriting the output**:
		it is `#104` / `DDRBHD5` reaching real data, and STATUS records there that
		no legal form clears it. **Why this is first contact and not a
		regression:** the six bundles in `xlib/` are lint-clean only because
		`dev/xcsv` and friends have **no non-local imports at all**, so the
		emission path had never met the linter. Filed as epiq `GADE1PY`,
		taskview `#134`.
	4. **`dev/xhttp/VERSIONS.md` does not exist** — `xconf`, `xcsv`, `xschema`
		and `xtest` all have one, and `doc/library-structure.md:34` makes it part
		of the per-library layout.
	5. **The human's own gate: validation against real code in Space-Traveller**
		(`#117`, due 2026-10-20). Not mechanical, and it is the stated condition
		for calling xhttp done.
	6. **Two red tests** (`7Z7DE78`, `websocket.send` type validation). A
		judgement call rather than a script error — `TESTING_RULES.md` forbids
		masking, and releasing a known-broken `send()` is the human's to allow.
	7. **`#115` is unimplemented**, so the one gate that belongs in the release
		path itself — refusing a library that depends on dev versions — is not
		there.
	Also stale, and cheap: `tools/release/README.md` still says the script
	*"fails at import"*; it no longer does, it fails at `bundler.bundle`.
	**(c) F21 was tolerated, not settled.** `imports` takes a modpath spelled with
	dots from the loop and with slashes from one test, and normalises both.
- **The pybundle rewrite is at the spec-edit stage: the tests are re-derived, and
	the spec has not caught up with what they proved.** The human wrote `DRAFT.md`
	as intent; `SPEC.md` is derived from it and written by an AI on the condition
	that every decision traces back to a draft section (`24e1856`, `d9528b0`). The
	first test pass found **12 spec flaws** (`doc/reviews/pybundle-tests-pass1.md`,
	`608621e`) — places where a test could not be written without a decision the
	spec did not contain. All twelve are appended to `SPEC.md` as *Decisions — test
	pass 1* (`03c0e75`), written append-only: 346 insertions, 0 deletions, so
	nothing above the new section moved. The tests were then **re-derived on
	2026-10-15** against those decisions — 138 in five files, superseding the 65 —
	which is what pass 2's review (`doc/reviews/pybundle-tests-pass1-2.md`) records.
	**Two things follow from that and neither is done.** First, five of the pass-1
	flaws are closed and **three are not**, all needing the human: the three
	name-import shapes with no stated answer (`F7KHKM8`), and mixed tab/space
	indentation (`S1G5037`). **Both halves of the indentation question were ruled
	on 2026-10-15.** *Mechanism*: *"Using the tokenizer's INDENT/DEDENT is a
	reasonable way of interpreting my intent. Checking strings exactly is not
	necessary"* — so D2 tracks blocks by matching the tokenizer's own INDENT/DEDENT
	tokens rather than comparing indentation strings, and the scope-tracking
	failure the string comparison caused cannot happen. That also settles D16's
	`indent`-as-a-string choice, which was made for precisely this reason
	(`EZAVYNM` records it). *Trigger*: anchor on the **root file** (or the first
	file that has indentation), warn if **any line** carries a different
	indentation type, and list every file that differs — over-firing deliberately,
	since the human calls it the simple approach to warning a user.
	**Two things the ruling does not say, both now on the record:** the scan
	should be over **statements, not lines**, or the warning fires on bracket
	continuation lines whose indentation Python ignores — six real ones in
	`dev/xhttp/test/test_parity.py` — and **D1 already provides the fix**, since
	`NL` vs `NEWLINE` is exactly that distinction; and the **root anchor is what
	makes the trigger catch the inline hazard**, because the callee disagrees with
	the root by construction. **Cost on XLib is zero**: across the 21 files under
	`dev/` that actually get inlined, mixed-leading lines are 0 and every one is
	unanimously tab-led, so the warning is silent here and matters when a foreign
	library is bundled. **Two further rulings completed the shape.** Whitespace-only
	lines are **ignored** — *"they don't affect how python runs in any case"* — and
	the report is **the first unexpectedly indented line per file**, *"since this
	is generally not the bundler's purpose"*. **Calibrated, not assumed: the rule
	is silent on everything this repo has produced** — 0 reported files across the
	21 inlined sources *and* the 6 bundles in `xlib/` the old bundler already
	produced; the 7 whitespace-only lines just excluded (all bare tabs in
	`dev/xhttp/_/`) were the only thing in the repo a literal scan would ever have
tripped on. One false-positive class remains unruled and costs nothing either
	way — **multi-line string interiors**, which by the human's own *"does not
	affect how Python runs"* reasoning should be ignored too, and which measure 0
	across the inlined files. What remains is **wording**, folded into `#127`.
	**The name-import questions were then answered by one ruling, and it reversed
	F13** (`#125`, epiq `F7KHKM8`). The human's chain: *"following python
	behaviour strictly would be the correct choice and would mean that every
	import involves a rebind"*, *"let's just say that every import, even
	non-local ones, gets a rebind"*, and finally **"okay, let's go with the alias
	solution"** once the collision evidence was on the table. The shape: **local**
	— import deleted, one rebind per name (`server__ship__defs =
	server__defs`); **non-local** — import rewritten with an alias (`from x import
	defs as A__defs`), no second statement; **local star import** — the same
	rebind per defined global, because a star import is *"just a more concise
	version of `from x import a,b,c...`"*. The two-statement form was tried
	first and dropped for a reason worth keeping: it does not remove the
	collision, it **relocates** it, because `from x import defs` binds `defs` at
	top level whether or not anyone rebinds it. **All three of the review's
	unanswered shapes are answered by this, verified together against real Python
	— 3 of 3 match**: star-import-then-shadowing gives 2 because the rebind is a
	*statement* and a later definition overrides it; a name the module does not
	define now traces, because the callee's own import was prefixed on the way in;
	and function scope works provided **a rebind's LHS is already prefixed and is
	not prefixed again**. Bloat measured at **+2%** (43 names, 1551 lines), and
	non-local imports cost nothing extra under the alias form.
	**Two consequences to carry.** `#127` **must not be executed as written** —
	its main item repairs D9/D19 by removing rebinding language, which the
	reversal made wrong in *direction*, and **D19's declined-warning paragraph may
	now be moot**, since three of its four collision sources are structurally
	prevented rather than merely unlikely and only the non-local star import
	survives. **The last undetermined output is closed** — the split rule:
	**dotted module imports** (`import a.b`) keep the statement and add one rebind
	(`import email.utils` + `A__email = email`); everything else aliases in place.
	The condition is precise: **the alias rule except where Python binds a name the
	statement does not spell.** The failure it avoids is half-silent — the alias
	hands the file the *leaf* instead of the *parent*, so `email.utils.parseaddr`
	keeps working by luck while `email.message_from_string` raises
	`AttributeError`. One occurrence (`dev/xhttp/_/helper.py:2`), so spec
	completeness rather than a blocker. **Bloat re-measured in bytes, on the
	human's correction that lines are the wrong unit**: prefixing lengthens every
	*reference*, not just the import lines, so the inflation tracks references —
	**+3% over 44 807 B**, from 0% (`_/server.py`, 10 imports, 0%) to 10%
	(`_/err.py`, 18 references in 832 B). It flatters XLib, whose `dev/` is
	shallow; the human's traveller example prefixes 4-character names with 13
	characters. Accepted cost, recorded as such.
	Second, **five edits the tests
	already answered are not written in** (`R9H4PVD`, `EZAVYNM`) — D16's field
	names, D13's argv clause, D1's clause, F18 and the counting correction, all
	of which stand, while the D9/D19 repair half of that pair is superseded.
	**Three decisions changed the tool's scope, not just its wording, so they are
	worth a second reader**: name imports are now supported, and the **alias ruling
	replaced the F13 mechanism outright** — local ones by a rebinding statement,
	non-local ones by aliasing the import, which is what **retires
	`NOT_A_MODULE`**; the function
	set grows from six to seven with `cli(argv) -> int`, which is what R5's "never
	closes a sink it did not open" was waiting for; and a **star import of a
	non-local module is left in place with a warning rather than refused** — the
	bundler will sometimes produce a bundle that does not work and says so on
	stderr. That last one is a deliberate accepted limit, and the append names the
	one-line change that reverses it; it is also the precedent the human's
	indentation ruling will read against. The human's reasons for the rewrite —
	pybundle is a tool and carries no versions; its earlier releases were removed
	before ever being committed; the last agent on it went in circles on the
	complexity — are in epiq `6MFX0Z1` (why: HISTORY.md 2026-09-30 for the
	original block). **Housekeeping the draft calls for is still undone**:
	`SPEC_new.md` is to be deleted once the implementation matches the intent, and
	until then it sits beside `SPEC.md` and `SPEC_old.md` looking equally
	authoritative.
- **`dev/xprod/` has no SPEC.md and no VERSIONS.md** — the only dev library
	missing both. Manual work for the human, parked on purpose; recorded as epiq
	`DCF9EHW` so the gap stays visible and does not become a quiet exception.
- **taskview #96 is ruled and blocked.** The human settled four things on
	2026-10-08: a separate `description` column on `tasks.csv`; exactly 2 tasks in
	full detail with the remaining pane space going to the condensed list; and
	the 2 always being the most urgent by due date (overdue first), regardless of
	day. Blocked on `AQQNPAN` — the CSV header declares 5 columns against 8-field
	rows, so a 9-column writer would land on a file whose header lies — and on
	the human's ruling that every other open taskview ticket lands first. Board:
	epiq `XNTVCEE` (Todo). The `description` field also collides with `E5MH4S2`'s
	open `priority`-column question; both grow the same file.
- **`dev/xconf/`, `dev/xcsv/`, `dev/xschema/`, `dev/xtest/` use `tests/`.** The
	ruling is `test/`, recorded in `doc/development.md`; the rename is epiq
	`2VD2XZC`.
- **`tools/tool_schema_cache.py:14`** names this machine's absolute path in a
	tracked file, which AGENTS.md forbids. The linter check that would catch this
	is epiq `7HP67R2` (Todo).
- **The `Q397WZG` / `9J30DNW` duplicate is resolved by relocation, not by a
	merge.** Both asked which worker the coding route should name, in two
	different lanes; both are closed and refiled on the Agents board as
	`G8B6T7V` and `P1H7VM4`, where the work lands. One decision, one board.
- **A stranded event is invisible on the machine holding it, which is why this
	went unnoticed for three days.** `epiq_issue_get` returned `GBNEWPS` as closed
	with a `Solution:` comment, and `QN1N82Y` as a filed ticket in Todo — both
	sourced from the on-disk pending file, **neither in any committed log**. A
	fresh clone therefore had no `QN1N82Y` at all, and had `GBNEWPS` open in Todo
	with no `Solution:` comment: an implemented, spec-backed xlint rule reading as
	work never started. The detector in `FZDMC84` compares pending against
	committed but cannot tell "this machine can see it" from "this is durable".
- **epiq pending events are drained; `AZHG0FK`'s "accepted risk" ruling is
	over.** 195 events were stranded on 2026-10-01 — XLib 454 committed / 60
	pending, Agents 113 / 135, with `mechanic` and `paul` holding *no* committed
	log at all — and 13 of them were `add.issue`, so a fresh clone got lane-moves
	and comments pointing at tickets that did not exist there. The named
	orphans were `CMGDFZF`, `VTJVHMY` and `QN1N82Y`, all three resolved
	2026-10-02. `epiq_sync` returns success with every flag false, so it reads as
	done and does nothing. The drain ran on 2026-10-02;
	`tools/epiq-pending.py` reports **1 event still stranded** as of 2026-10-08
	(a bare `create.contributor` carrying no ticket content).
	`AZHG0FK` assumed the loss window was a worktree prune — a missing creation
	with committed events referencing it is more severe than that. Draining
	another actor needs a session running as that actor, which `epiq_actor_assume`
	refuses unless the server was launched with that name. The mechanism is
	per-actor and has no fix: each actor writes to
	`.epiq/events/<actorId>~pending*.jsonl`, which `.gitignore` deliberately never
	commits, and `epiq_sync` only ever drains the calling actor's own log.
- **Two worktree hazards, both reproduced 2026-10-08.** `check-clean` answers
	`clean` for a dirty file in a worktree — a worktree's `.git` is a *file*, so
	`nearest_git` walks past it to the parent repo and reads the wrong status
	(`8FVW49J`). And `.agents/` is gitignored, so a fresh worktree has no
	`claims.json` and claims resolve to the main checkout only. **Corrected
	2026-10-08**: an earlier line here said `check-clean` *refuses* worktree paths
	with "paths span multiple repos". It does not; that error needs two different
	repos in one call, and `.opencode/agent/` never triggers it because `abspath`
	does not follow the symlink.
- **The agent-file zero-stats problem is ruled against, not just fixed.**
	`.opencode/agent/` is a symlink into the Agents repo, so an agent-file ticket
	filed on this board reads as zero commits however it is committed; 16 were
	refiled on 2026-09-30, which fixes the 16. The filing rule — file on the board
	of the repo where the change lands, decided by which repo versions the file —
	now lives in `AGENTS.md` under *Working on a ticket*, which is read before a
	ticket is filed rather than after. What it cannot do is catch a ticket filed
	without it: the choice is made through the epiq MCP, not through a repo tool,
	so nothing local can intercept it. That is the one rule here left as prose.
- **The best column alignment in this repo is module-docstring prose, not code.**
	`dev/xcsv/xcsv.py:24-30` and `xlib/xcsv_1_1_0.py:97-103` line up five
	exception names with literal `#` characters **inside a `"""` docstring**,
	where Python sees no comment at all. Found 2026-10-09 while re-measuring the
	alignment ruling, and it is the cause of two wrong figures I reported earlier
	this session: the masking handled single-line strings but not docstrings, so
	those 10 lines were counted as aligned code comments. `doc/style/python.md` has
	no sentence on docstrings — formatting, length, or what belongs in one rather
	than in the SPEC. Same shape as `DDRBHD5`/`BX56XRY`/`13QYCT8`/`KJKEQ01`: a
	convention in wide use with no text behind it. epiq `HRGFRWX` (Todo).
- **Houserule ruled 2026-10-09, second half: alignment counts only at very high
	comment density, and a comment belongs on the line before what it explains.**
	Aligned same-line comments count only where **comment density is very high**;
	inline comments should **usually be avoided** in favour of a preceding line;
	and the single space applies **only to inline comments**, i.e. to those allowed
	to stay inline at all. Such cases are rare because high comment density is
	itself often a violation of *comments are for why, not what or how*.
	**Corrected 2026-10-09, twice.** I first reported all 134 aligned comments as
	violations, then 31-in-9-blocks as legitimate; both were wrong because the
	docstring masking missed. Corrected: **91 lone inline comments** (74 of them
	`def`-line comments owned by `HRCQSV4`, **17** on ordinary code) and **5 real
	blocks** of 2+, not 9 — and **2 of the 5 are already single-spaced and
	compliant**. The ruling's default is existing practice: **528 of 663** tracked
	Python comment lines (79%) already sit on their own line. epiq `BSFQYPF`.
- **Houserule ruled 2026-10-09: spaces are never used for alignment.** Tabs if
	alignment is wanted; avoid alignment where possible. A spilled function
	signature becomes ordinary tab indentation, not columns — `func(` alone,
	arguments one tab deeper, `)` at the `func(`'s own indent — because
	**renaming a parameter breaks a space alignment and cannot break an
	indent**; that fragility is the stated reason. **Not yet written down**:
	`AGENTS.md`'s `## Houserules` (`:137-139`, one entry) and
	`doc/style/python.md` are both untouched, and the `0P2TVAM` precedent put that
	houserule in both files. Measured scope: **369 lines in 47 tracked files** —
	134 `.py` space-aligned comments, 135 Markdown alignment prose/tables,
	100 other (epi `BSFQYPF`; reformat `F8XBH1F`). Two questions the ruling does
	not answer: **comment columns** (the biggest category, and the fragility
	argument applies to them as much as to signatures) and **Markdown tables**,
	where tabs do not render as padding so "use tabs" has no working answer.
	Three xlint tickets now hang off this ruling: `BSFQYPF`, `13QYCT8` (whose
	`code  +#` exemption the ruling deletes — outside data a double space is a
	typo by construction), and `1YPFZYH`.
- **xlint's `check_def_one_line` is wrong in 74 of 74 cases.** It reports
	"function definition split across lines" for **74** `def`s across tracked
	`.py` and **none** are spills — every one is a single-line `def` carrying a
	trailing comment, because the closing pattern is anchored `\s*$` (`:130-140`).
	A 100% false-positive rate, and all 74 sit in `tools/taskview/test/`, which
	`AK633QC` shows is invisible to a plain `xlint .`. It also **bans the exact
	tab-indented signature shape the new houserule permits**, so the ruling and
	the check cannot both stand and the check cannot be the survivor. The
	trailing-comment fix is one line and converts 74 findings to 0 — worth
	landing before any redesign. **Split 2026-10-09**: the human ruled the 74
	lines are bad taste but not spills, so the one-line false-positive fix stays
	here and the new rule is `HRCQSV4` — where **`class` lines turn out never to
	have been checked at all** (`_DEF_PREFIX_RE` matches `def` only), so the 0
	count is a coverage gap rather than a clean baseline. epiq `1YPFZYH` + `HRCQSV4`
	(Todo).
- **xlint runs `check_trailing_whitespace` on `.py` and not on `.md`.**
	`check_file` (`:198-222`) branches by suffix: five checks for `.py`, two for
	`.md`. So Markdown hard breaks — two trailing spaces, a documented CommonMark
	feature — are permitted by omission rather than by decision, and **58 tracked
	`.md` lines carry trailing whitespace, 56 of them exactly two-or-more spaces**.
	Corrected 2026-10-09: I first wrote that this contradicted the double-space
	check; it does not, because the check is simply absent on `.md`. epiq
	`KJKEQ01` (Todo).
- **xlint has no mid-line double-space check, and the rule as stated would
	fight the repo's own comment alignment.** Not implemented — no check, no
	`--no-` flag. The human's condition is that it **must not fire inside data**
	(inline strings and the like), and that condition is most of the ticket: a
	prototype goes **116 → 586** findings repo-wide, of which **134 are the
	`ClassName    # comment` column layout** used across `dev/xcsv`, `xlib/` and
	`dev/xschema` — house style, not sloppiness. 120 more are SPEC.md alignment
	prose, 94 are string literals, 7 Markdown tables, 5 inline code spans. So
	exempting "data" is a **ruling, not a detail**, and the rule is unwritten:
	`doc/style/*.md` has no double-space sentence at all, and on the narrow
	sentence-period reading (`[.!?:]  +[A-Za-z]`) the repo is already clean at
	zero hits. Two implementation findings worth keeping: exempt by
	**replacement, never deletion** (deleting `` `<REF> ` `` from
	`...is \`<REF> \` — ref...` leaves two spaces and the line explodes: 1879 vs
	586 findings), and `_fence_exempt` (`:81-120`) is already built for the `.md`
	branch but feeds only `check_space_indent_exempt`. epiq `13QYCT8` (Todo).
- **xlint has no check for a single trailing blank line, and its two
	file-ending checks do not compose into the rule either states.**
	`check_final_newline` (`tools/xlint/xlint.py:142-145`) requires the file to
	end in a newline and `check_double_blank` (`:50-55`) rejects two consecutive
	blanks — so `import os\n\n` passes both, being a real last line, one blank,
	and a present terminator. Two blanks at the end *is* caught, which is the tell
	that `\n\n` is an oversight and not a policy. **Four tracked files carry it**,
	none currently flagged: `tools/taskview/taskview.py:765`,
	`tools/taskview/taskupdate.py:298`, `tools/bbprs/README.md:193`,
	`doc/reviews/pybundle-review.md:336` — the tool's own two entry points
	included. A prototype adds 4 findings repo-wide (116 → 120) and loses none.
	Same root as `DDRBHD5`: each check was written against its own symptom rather
	than against the rule, so neither composes. Also unenumerable — neither
	`missing final newline` nor this has a sentence in `doc/style/python.md`.
	epiq `BX56XRY` (Todo).
- **xlint's merged-imports rule is unsatisfiable for aliased imports.** The
	human ruled on 2026-10-09: **aliased imports get their own line, and should
	generally be avoided where avoidable — but xlint must handle them
	correctly.** The code change is now unambiguous (detect ` as ` explicitly,
	give aliased imports a branch, `prev_plain = False` so they do not
	propagate), and a prototype is inert on tracked code: 116 findings before and
	after, byte-identical. The ruling's second half is still open — whether
	"avoided when possible" is prose or a new check; mechanically it means "the
	alias never appears", which would fire on `import numpy as np` everywhere.
	`check_imports` (`tools/xlint/xlint.py:190`) decides plain-vs-dotted by
	testing the module text for a dot, and `import x as y` has no dot — so an
	aliased plain import is classified plain, flagged, and propagated as a
	mergeable predecessor. `import json` / `import math as m` /
	`import collections` produces two findings and **no rewrite that clears
	them**; the merged form `import json,math as m,collections` is legal Python
	(`ast.parse` accepts it, binds `json`/`m`/`collections`) but still reads as
	plain under the classifier. The two aliased forms are treated oppositely for
	no reason but the dot: `import a.b as c` escapes the rule, `import math as m`
	does not. `doc/style/python.md:20-23` covers plain and dotted and says nothing
	about aliases, which is how the linter filled the gap on its own.
	**Corrected 2026-10-09**: an earlier entry here said two shipped fixtures
	already violate it, making this non-latent. Wrong — both fixture findings are
	unrelated (`stdlib/main.py:3` is a plain/plain pair with the alias *after* it;
	`alias/main.py:3` is the `from`-import same-module check), so the
	unsatisfiable input has **zero occurrences in tracked code**. `tools/xlint/`
	has no test file at all, which is how it went unnoticed. epiq `DDRBHD5`
	(Todo).
- **xlint does not lint tests, and the house rule for test folder names is
	inverted relative to it.** `is_ignored` (`tools/xlint/xlint.py:28`) excludes any
	path part named `test` — the repo's own convention, so `xlint .` skips every
	test file and reports 0 while violations sit in `tools/taskview/test/` and
	`dev/xprod/test/`. **The 109 / 103 / 5 / 1 breakdown recorded here is stale
	as of 2026-10-14**: `tools/pybundle/test/` and its fixtures were deleted in
	`5e87ae8`, so that term is out of the sum and the total needs re-measuring
	before anyone quotes it. `tests/` — the name
	the rules call wrong — is *not* excluded, so `2VD2XZC`'s rename would move
	four linted libraries out of coverage. Needs a decision: narrow the
	exclusion to foreign test data, or write down that tests are exempt.
	`AK633QC`; `XCKN0AT`'s pre-commit hook inherits it verbatim.
- **Task scheduling**: 4 high-importance tasks have no due date at all (#52, #61,
	#63, #75), and everything due today has by now gone overdue — 10 open tasks
	are past due, and that number moves hourly. The store is the record; see
	`TASKS.md` for this workspace's two.

## Settled — not to be reopened without cause

- **The board is the unit of work.** The human's ruling, 2026-09-30: one ticket
	per independent piece, its own feature branch, one commit per ticket,
	subject opening with the ticket ref. **Todo** is pending, **In progress**
	means the human has ai-ok'd it, **Done** means the agent finished it. Agents
	move their own tickets to Done. A ticket leaves Done when the human reviews
	and approves it — only then may an agent merge it to master and delete the
	branch. This overrides the epiq skill on two points: Done is not "merged",
	and the merge is the agent's action once approval is given.
- **Two tracks for development** (human, 2026-09-30). Feature work keeps the
	spec pipeline; anything whose goal, scope and acceptance fit in a ticket
	description runs as a ticket-is-the-spec, which is the default. The spec
	pipeline is not abolished — it is pipelined through epiq as separate commits
	and tickets. Neither track is written into `AGENTS.md` yet: epiq `0J8YBYH`.
- **`tools/tmux-xlib.sh` killing the session is intended**, on start and on exit —
	the panel takes down everything it started, so nothing is left running in the
	background. What it needs to be safe is a session name that means something: the
	name is derived from the target repo's path, so one repo's launch cannot kill
	another's panel. epiq `5DZ8NB1`. The live session named `xlib` predates that and
	is not what the XLib launcher opens any more.
- **Versionless imports in dev-folder tests are correct** — a test imports the
	code being developed. AGENTS.md says so explicitly now; the old wording read
	as a blanket ban.
- **The four `doc/reviews/pybundle-*.md` files and the empty `tools/pybundle/_/`
	stay.** The facts are written down in `doc/reviews/README.md` and here; the
	ruling was to note them and leave the files in place.
- **pybundle's missing versions are a ruling, not an oversight** (human,
	2026-10-01). pybundle is an XLib tool, is not meant to have versions, and
	**did have releases that were deliberately removed before ever being
	committed**. So `doc/reviews/pybundle-23efebb3.md` §14 reading the
	`1_0_0`–`1_0_3` entries in the old `VERSIONS.md` as "fiction" drew the wrong
	inference from a right observation — the releases were real, then removed. The
	review files stay as they are; what was corrected is the reading of them, now
	in epiq `6MFX0Z1`.

## Open questions for the human

1. `dev/xprod/` — SPEC.md + VERSIONS.md, or fold into another library? Parked as
	your manual work, epiq `DCF9EHW`.
2. **`Z491RDN` — is the patches file generated at release or hand-maintained at
	merge?** Generating it from `git log <prev-tag>..<tag>` cannot drift; a
	hand-kept file drifts by exactly the amount nobody remembered. Recorded
	because it is a design decision with reasoning that does not belong only in
	a conversation. Does Traveller tag releases? Without a boundary the patch
	notes cannot be sliced.
3. **The last stranded epiq event needs a session, or it needs epiq changed.**
	The mechanism is understood — per-actor logs, and `epiq_actor_assume` refuses a
	name its server was not launched with — so this is no longer a mystery but a
	decision: one session per stranded actor, which means the human launching it,
	or a change to epiq itself. **1 event remains stranded**, a bare
	`create.contributor` for an actor that registered and stopped, carrying no
	ticket content (`tools/epiq-pending.py`, 2026-10-08). Low stakes as a number;
	it stays open because the *mechanism* has no fix, and the next agent to exit
	without syncing restarts the count.
4. **Should `release.py` tag or commit a release?** It currently does neither,
	there are zero tags in the repo, and the README's scope section may mean that
	is deliberate. If deliberate it should be written down; if not it belongs in
	`1ZY2Q5Q`. Related: `Z491RDN`'s "entry written when the change reaches master"
	has no tooling behind it.
5. **Three pull requests rewrote `STATUS.md` from the same base, and merging them
	meant three hand-resolutions.** They conflicted because each was written as a
	snapshot of the moment before its own merge, so the merged file had to pick one
	version of every shared claim. That happened twice already (#1/#11, then this
	run) and will happen again while state-file rewrites are a per-ticket
	deliverable. Worth deciding whether a STATUS.md rewrite is a ticket of its own
	or a final step of the merge, since the second stops two agents racing for it.
5. **Should `doc/style/prose.md` bind dispatched workers too?** The rule file
	is reachable through `AGENTS.md`, which every agent reads, but a subagent
	runs from its own prompt in `.opencode/agent/` and does not necessarily get
	`AGENTS.md` in context. If the prose rules are meant to apply to worker
	output too, that needs a mechanism; today they bind the agents that read the
	repo rules. `KDX7KWJ` closed without deciding it.
6. **`xlib_dev` shipped to master** (taskview #112 done, epiq `ASTXNPG` Done,
	commit `b0214a4`, 2026-10-10). `from xlib_dev import xcsv` runs real code
	against `dev/xcsv/xcsv.py` instead of the newest file in `xlib/`, resolved
	through an `__getattr__` mirror of `xlib/__init__.py` so adding a library
	costs nothing and the caller gets the real module object. Three questions I
	raised are closed: that shape rather than a file per library; the "released
	never depends on dev" enforcement split into **#113** (xlint gains
	repo-specific rules) → **#114** (the actual rule), plus **#115** (release.py
	refuses a library with a dev dependency) — with the human correcting my
	framing, which had been wrong: **dev → dev dependency is fine and wanted**,
	only the dev → release boundary is policed. The other agent's in-flight
	xlint work was kept off the branch and restored to master's working tree
	uncommitted. **master is one commit ahead of origin and unpushed.**
7. **Correction: there is no broken namespace-package import in `dev/`.** I told
	the human on 2026-10-10 that `import dev.<lib>` was unreliably importable on
	py3.14 and built an mtime/`FileFinder` theory on top of it. All of it was my
	own typo — I wrote `dev.xlsx.xlsx` (`dev` + `xlsx`) instead of
	`dev.xcsv.xcsv` (`dev` + `xcsv`). There is no `dev/xlsx`, so every failure was
	an honest `ModuleNotFoundError` for a directory that does not exist, and the
	mechanism I attributed to it was never exercised. Verified 10/10 in every
	configuration afterwards. No `__init__.py` is needed and no restructuring of
	`dev/` is required. **Why it matters beyond this task:** the failure mode was
	an unverified premise promoted to a confident root cause, with real-looking
	detail attached. A "not reproducible, here is my theory" report should have
	came first, and the cheapest check — printing the string you were importing —
	should have come before the theory, not after.
8. **A dotted non-local import leaks one unprefixed name — RULED 2026-10-17:
	accept it and write it down** (`SPEC.md` D31). D20 keeps `import a.b` verbatim
	because python binds the *parent*, which the statement does not spell, so
	aliasing would hand the file the leaf: `email.utils.parseaddr` would keep
	working by luck while `email.message_from_string` raised `AttributeError`,
	which is the half-silent failure the ruling exists to prevent. The price is
	that `email` lands at the bundle's top level unprefixed, and **it cannot be
	removed** — a name python does not bind under the statement's spelling is
	reachable only through `__import__` or `sys.modules`, and D7 excludes dynamic
	imports on purpose. **No warning**, which is D19's posture applied to a second
	case: unprovable, and no failure observed — unlike D9's star import, where the
	behaviour was at risk. One occurrence in everything this repo inlines
	(`dev/xhttp/_/helper.py:2`), and the bundle it produces works. **The one cost
	worth stating** is not cosmetic: a file that defines a global of the same name
	has its meaning changed, because the definition is prefixed and the bare name
	stays the module. It is also a second class of unprefixed name alongside the
	non-local star import D24 warns about.

## Pointers

- Process: `doc/development.md`. Code rules: `AGENTS.md` + `doc/style/*.md`.
	Library structure and conventions: `doc/library-structure.md`. Library maps:
	`<library>/SPEC.md`. Plans: `doc/plans/README.md`.
- Tasks: `TASKS.md` (this workspace), taskview ids in
	`~/.local/share/taskview/tasks.csv`, epiq refs on either board. A taskview id
	and an epiq ref look alike and are different things.
- **Which board a ticket goes on is a rule, not state** — `AGENTS.md` under
	*Working on a ticket*. Short form: a ticket belongs on the board of the repo
	where its change lands, and relocating between boards means close-and-refile
	because a ticket cannot be moved across two separate epiq projects. The
	old→new map for the 2026-09-30 split is on `58MXTGY`.
- Shared user context and per-agent state: `.agents/` in the Agents workspace.
- Reviews: `doc/reviews/` (read its README first). Audits: `doc/audits/`.
dirty-test
