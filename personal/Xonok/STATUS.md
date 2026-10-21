# XLib STATUS — master file

The current picture of this workspace: what exists, what is being worked on, what
is blocked, and what needs a decision. Present tense only — anything worth
reading in six weeks is in `HISTORY.md`. Details live behind the pointers at the
bottom; this file stays a summary.

## Convention (all agents)

- Update this file when you start or finish something, or when your progress
	estimate changes. One line per work item: what, who, % done, where to look.
- **These state files are written by the secretary, at merge time.** A feature
	branch does not carry them — a Done ticket does not carry `STATUS.md`,
	`TASKS.md` or `HISTORY.md`. The rule and its reason are in
	`doc/state-files-history.md`. Ruled by the human, 2026-10-21.
- Finished items are appended to `HISTORY.md`, not moved to a "Recently done"
	section here. The open list simply loses them. History is append-only:
	nothing is rewritten or removed without the human's sign-off.
- The % done number is **your own estimate of how done you think it is** — rough
	is fine, stale is not.
- Keep the Snapshot date current. It is the basis of the file, not a log.

## Snapshot

Basis: `master` at `54e9621` (2026-10-21), **snapshot taken 2026-10-21**, **in
sync with `origin/master`** — **the skynet display now fits the pane it is in,
and says how much it left out (PR #58 and PR #59, merged on the human's
authorisation).**
**Herdr is the human's active workspace manager now, and tmux holds the passive
panels** — the human's own split, 2026-10-21: *"I use herdr for actively doing
stuff and tmux for passive panels… herdr has an extra panel for keeping track of
agents and letting me quickly switch between them, which is useful, but takes
space."* **Herdr 0.9.1 is installed, and its opencode integration (v12) is
installed as of 2026-10-21**, so herdr knows each pane's session id instead of
reading the screen. **The agent names are in herdr's sidebar now**: they were
always in herdr's model — it captures the OSC title every pane writes, as
`terminal_title` — but the default agent rows never asked for it, and herdr owns
the outer window title, so nothing on screen showed them. **Measured in a real
window, not read off a document**: the pane reported
`agent_session.source = "herdr:opencode"` with the same session id marduk's
registry names (`ses_ea2b02f8…`), and `screen_detection_skipped` was true.
**PR #50 carried the second half of the `news` repair, which the PR #47 repair
did not actually fix; it is merged, on 2026-10-20 as `f12ebd5`.** PR #47 is
merged and pushed, and it carries the two
coordination fixes: `K93Z39B` (the `news` command) and `8FVW49J` (the
`check-clean` guard). PR #44 is merged and pushed too, and it carries two
fixes of its own: `XP56NNC` (the linter inside a worktree) and `2X3PZT3` (the
gate that never ran there). PR #42 (`YFJZRYC`, the html lint implementation) is
merged and pushed, so xlint lints `.html` on master and the human can run it
over Traveller. PR #36 (`YFJZRYC`, the html lint *rules*) went in before it, and
so did PR #34 (`MY4ZS5D`, the `git checkout` ban and the 2026-10-18 state
files). The Traveller acceptance test has been run — the bundle was produced and
does not run — **though the artefact is no longer on disk, so a repeat run is
needed to see it again**.

**Three things this sweep found, and all three have moved since. `RX5H4P3`
reproduced — and is fixed** (a bundled function parameter that shadows a module
global was renamed on the def line and not in the body, so the bundle compiled
clean and then raised `NameError` at the first call; the spec already ruled it,
R4, so it needed an implementer, not a decision). **The Traveller acceptance run
found it a second time and fixed it with it** — a parameter is a name the
function binds, so it is not translated (spec **D40**), commit `a9b9fe5` on
`fix/JD9DWVN-bundle-traveller` (PR #76). **The repository's own guard over its
test layout was red — and is green now**: `tools/run_tests.py`'s `SUITES` did
not list `tools/modelbench/test`, so eight modelbench test files were
unreachable (epi `QPDJ8RF`). **Fixed and merged as `b1dd369` (PR #77)**, and the
guard then found a **second** defect it had been hiding: two of the eight had
no `__main__` block, so running either on its own exited 0 having run nothing.
**And `2VD2XZC`'s blocker is gone** — the rename it was waiting on is now a
pure rename, and the ticket's `ai-ok` is the human's to give. The three were
taskview `#178`, `#179` and `#180`; the first two are done.

**Five more merges on 2026-10-20, on the human's authorisation** ("you can
commit the changes that are on master and whatever else makes sense"):
**PR #50** (`K93Z39B`, the `news` repair, merged as `f12ebd5`),
**PR #51** (`TAQ74SC`, the state-file drift sweep, merged as `671b150`), and
**PR #52** (four commits — the xtest standardisation, the absolute-path check
on Python files, and the category vocabulary — merged as `df34b07`).
**One command now runs the repository's tests: `python3 tools/run_tests.py`,
934 tests across 14 suites.** The 6 failures are the known
`ContentNegotiationTest` — xhttp gzips regardless of `Accept-Encoding`, epiq
`BFNRBG7` — and they fail the same way under plain unittest. **The category
vocabulary is thirteen values, all lowercase with no dash or space**, and XLib
work is scoped to `xlib` with the part of XLib it is about as the second
level.

**`agent-coord.py` had two defects that made the coordination tool report
something untrue. One is fixed and on master; the other was not, and its
repair is PR #50.** The `news` command — the only channel that carries a rule
change out to the agents that have not read the file — reported "no new
guideline changes" for every workspace and **took the claims of every agent on
the machine with it** when it ran. Four breaks, all measured against the live
tree: the workspace resolved to `$HOME`; the migration dropped every claim whose
owner was not a key in `ids.json`, and a claim is owned by an agent id while
`ids.json` is keyed by session key, so the two key spaces never met; the rule
files were globbed at `style/*.md` while XLib keeps them at `doc/style/*.md`;
and the session key was the service's pid, so every session shared one
identity, one notes file and one rule cursor. **The claims-wipe is genuinely
fixed**, and the rule files are found. **The workspace resolution is not**, and
the reason is worth stating because the fix was verified and still did not
hold: the repair settled on the opencode *client* by walking this process's
ancestry, and it assumed the client is an ancestor of the tool shell. Under
opencode 2 it is not — the shell descends from the shared service, and the
client is a separate process — so the walk finds the service, whose cwd is the
home directory, and the session resolves to `/home/xonok` again. **Measured
live on 2026-10-20, in a session shaped like this one: `news` printed `no rule
files found in /home/xonok — nothing checked`, 0 rule files.** The
verification recorded on the ticket was taken in a session whose ancestry
happened to hold a client; the topology this machine actually runs — one
service, four clients, no client in any tool shell's ancestry — was not
covered. **So the `git checkout` ban, which `news` was carrying, still cannot
reach a session shaped like this one.** PR #50 finds the client by what it says
about itself: it names the session it serves in its own arguments, and it works
in the directory the session works in. The service is never a candidate, and
the session key follows it, so two windows are two sessions again. The second
defect, `check-clean` reporting **clean** for a dirty file inside a worktree —
the guard that stops two agents editing one file, failing open — **is** fixed
and on master. **36 tests in `tools/test/test_agent_coord.py`; 11 mutations of
the repair, each killed by the test that names it.** **Verified on the live
state with PR #50's code: `news` finds the 41 rule files, the workspace
resolves to `/storage/GitHub/Fun/XLib`, and the machine's claims are still
there.**

**Task updates 2026-10-19:** #117 (xhttp release survival) marked done — the released
`xhttp_1_0_0.py` survives Space-Traveller use. #111 (Discord access design) marked done;
new task #138 (Discord access setup) added. #139 and #140 (the html linter and the
html bundler library) **were open in the store and missing from `TASKS.md`
entirely** — both are there now, with the html rules ruled. **#139 is done: the
html linter is written and **merged** — PR #42 is on master as `5c1865e`, so the
html rules can be run over Traveller today.**
#141 (mechanize the checkout ban) now has a wider target: the ban covers `git reset
--hard` and `git reset --merge` as well, so the guard has to catch those too.
**#144 (the linter inside a `.work/` worktree) is done — PR #44.**

**The style gate did nothing in a worktree, and the linter it calls would have said
`clean` anyway. Two mechanisms, one failure, both measured.** **The linter**
(`XP56NNC`): `xlint .` inside `.work/<ticket>/` reported `clean` while checking
nothing — the outer repository's `.xlintignore` lists the worktrees it holds, the
rule reached into the worktree through the upward walk that finds ignore files,
and every file in it was excluded. **The hook that runs the linter**
(`2X3PZT3`): `core.hooksPath` was the *relative* path `.git/hooks`, and in a
worktree `.git` is a *file*, so the path did not resolve to a directory and git
found no hook to run — **the style gate and the ticket-ref check both did
nothing in a worktree**, and a worktree is where the work happens since the
human's 2026-10-01 ruling. **Fixed in PR #44**: the walk for ignore files stops
at the checkout that owns the path (a worktree's `.git` is a file, and a lookup
that recognised only a directory walked straight out of it); the hooks are
installed into the shared git directory and `core.hooksPath` is left at git's
default; and a run over an excluded path says **"nothing checked"**, naming the
rule that excluded it, instead of printing `clean`. **Eight new tests; the suite
is 98 green.** **The gate's own output at the repository root is unchanged** —
the same single finding, an absolute path in this file, which this change fixes.

**xlint lints `.html` now.** The three rules the human ruled on 2026-10-19 (epi
`YFJZRYC`) are written: **unclosed tags (strict)**, **closing tags that should
not be** (all three readings) and **bad indentation** (depth mismatch, and
spaces-not-tabs, with the depth measured in the file's own unit). The code is
`tools/xlint/_html.py` — a tokenizer, one walk over the tags, and the depth
rule — imported by `xlint.py`, with a `--no-html-*` flag family (seven flags) and
`.html` in `_ALL_SUFFIXES`. **Twenty-three new tests; the suite is 90 green.**
**Measured on the acceptance corpus (Traveller's 27 html files and Mallesne's
one): unclosed 0, stray closer 0, depth 774** — 589 of them the one systematic
off-by-one, and the single -1 is `main.html:134` exactly as the earlier
measurement said. The earlier measurement said 773 and 588: the one-finding
difference is a detail of a script that was never kept, and the shape matches
(the same 184 deeper findings, the same single -1). **Trailing whitespace reads
7 under xlint's own generic rule, not the 3 the measurement script found: the
difference is four lines ending in a *tab*, which that script's check did not
see.** `doc/style/html.md` states the rules.

**The `git checkout` ban grew a second ban and a measured exception.** `git reset
--hard` and `git reset --merge` are now banned in `doc/working-tree.md`, because
both discard work from the working tree: `--hard` reverts edited files, deletes
staged-new files from disk and can orphan an unpushed commit, and `--merge`
deletes a staged-new file while looking like the gentler option. **Plain `git
reset` is not banned, and the reason is the measured one**: it does not touch the
working tree at all, so every uncommitted edit survives it — what it resets is the
index, so a file another agent staged becomes untracked and the next commit
silently omits it. Dangerous, but silently rather than destructively. The
measurement table is in the document.

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

**The working tree is not clean, and what is in it is not pybundle's** — the OpenCode
v2 migration of marduk, oc-agent and skynet, which sat dirty here from 2026-10-16 and
**landed as `8bf0ef3` on the human's instruction on 2026-10-17**. The board ticket
(`W06YDEQ`) was filed at commit time, because the `commit-msg` hook accepts only a real
epiq ref and no ticket covered the work — the human chose filing one over bypassing the
hook. **94 tests in `tools/marduk/test/` came with it, xlint clean, four fixes
mutation-checked.** What the landing deliberately left behind is
`tools/marduk/_/port_watcher.py`, now dead code that nothing references, and
`tools/marduk/SPEC.md`, which still describes the port-file protocol and contradicts
the code in about twenty places. **Neither is filed yet** — a rewrite of that SPEC is
planner work, and it is the item most likely to mislead the next reader. The only file
still dirty is `dev/xhttp/xhttp.py`, kept out of the commit on purpose. The pass-3
material is
kept below for what it settled: 188 tests in six files plus
`doc/reviews/pybundle-tests-pass1-3.md`, committed as `de4f70b`. The pass-2 history is
kept below for what it settled: 138 tests in five files plus
`doc/reviews/pybundle-tests-pass1-2.md`, 9 files and 1102 insertions, with the four
rulings recorded in the commit body, including that **F13 was reversed** — which is
why 138 is not a stable number and 188 is the current one. xhttp arrived in
`dev/` from Space-Traveller on 2026-10-10; its root is clean — documentation,
`xhttp.py`, the internals in `_/`, the suite in `test/`, and `compare/` holding
the temporary RFC comparison material (`ba84849`). **The suite is green: 223
tests, 0 failures, 1 skipped** as of 2026-10-18 — the two failures it carried
since 2026-10-12 were tests that had never been written, not a defect (see
*In progress* and `7Z7DE78`). Its design
record lives at `dev/xhttp/SPEC.md`. **xlint reports clean over the
whole repo — and that claim was stale, because it was carried by a defect that no
longer exists.** It used to say that xlint "skips every directory named `test`, so
its violations are invisible to it" (epi `AK633QC`). **That ticket is closed and
the exclusion is gone**: `_BUILTIN_EXCLUDED` (`tools/xlint/xlint.py:29`) is
`{"__pycache__", ".git", "node_modules", "xlib_legacy"}` and the skip is now a
per-repo `.xlintignore` list. Verified by running it, not by reading it — a file
with trailing whitespace inside a directory named `test` **is** reported. The
claim was repeated in `TASKS.md` (`#134`) and in `HISTORY.md`; the fix landed and
the records did not follow.
**Nothing can be released at all right now**, for two independent reasons: the
dev-folder path fix landed in `c657694` (`1ZY2Q5Q`), but `release.py` imports
the bundler at module scope and **the bundler was deleted** in `5e87ae8`, so
the script now fails at *import* rather than at bundle time. Read Blocked before
trusting a release. **195 epiq
events were stranded on 2026-10-01, 13 of them issue creations**; the drain ran
on 2026-10-02 and `tools/epiq-pending.py` reported **1 event still stranded**
(a bare `create.contributor` carrying no ticket content), confirmed 2026-10-08 —
**and reports 0 stranded events now, re-measured 2026-10-20.**
**No pull request is open**: PR #50, the `news` command's workspace resolution
(`K93Z39B`), was merged on 2026-10-20 as `f12ebd5`, and PR #33 (`ZRTSZMB`, the `ctx` opencode-2.0 fix)
was merged on 2026-10-18 as a rebase merge with the branch deleted, `dc078ce`, and
with it the seven Done-lane tickets whose commits are on master are closed: `ZRTSZMB`,
`7Z7DE78`, `NJ529TQ`, `GADE1PY`, `W06YDEQ`, `2X0B2XW`, `VC9QWYY`. Before that, four
tickets were approved by the human on 2026-10-08 and merged as a flat rebase sequence,
no merge commits: `AFVAWRX` (#26), `3EEXMRK` (#21), `FZDMC84` (#23), `4N5J1AS` (#25).
Before them, six merged on 2026-10-02 — `58MXTGY`, `EY72YA9`, `X06YVNP`, `CMGDFZF`,
`0ZSB1DP`, `PMRBFR3` — and twelve before that. `doc/development.md` is the canonical
process document — plan → spec → tests → implementation → review, each stage entered on
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
- Live coordination state: `python3 tools/agent-coord.py news` (changed rule
	files). **There is no `status` command any more** — the file-claim mechanism
	was retired on 2026-10-21 (epiq `5S8FY10`), and with it the only way to ask
	who held what. `check-clean` is the guard that remains.
- **There are two epiq boards, one per repo, and 16 tickets moved between them
	on 2026-09-30.** The filing rule is that a ticket belongs on the board of the
	repo where its change lands, because that is the only board whose state
	branch can see the commit. See `AGENTS.md` under *Working on a ticket* for
	the rule and `58MXTGY` for the ref map.

## In progress

| Item | Who | Done | Where |
|------|-----|------|-------|
| **pybundle rewrite** | human (intent) / AI (spec) | **IMPLEMENTED and committed 2026-10-17. The acceptance test passes 2026-10-21: the bundled Space-Traveller runs, and answers HTTP exactly as the unbundled one does. 212 tests green in `tools/pybundle/test`.** The five modules are in the tree and tracked. **What remains is two things, neither of them the implementation:** the shim option (`#133`, the human's own words, future work) and the housekeeping `DRAFT.md` asks for — **`SPEC_new.md` is still in `tools/pybundle/` beside `SPEC.md` and `SPEC_old.md` with nothing marking which is current** (taskview `#183`). The spec carries its own decisions: D20 (alias, reversing D9 and F13), D21 (INDENT/DEDENT), D22, D23, D24, D25, the 2026-10-17 set D27–D34, D36, D37, and the 2026-10-21 set **D38–D43** — the five the acceptance run found. **PR #76 is open with the acceptance repair, waiting for the human's review.** | epiq `6MFX0Z1`, `86CDJV2`, `JD9DWVN`, `VQKH390`, `RX5H4P3`, `14VP9PT`, `AYB2896` |
| **xhttp** | human | **Released `1_0_0` 2026-10-18** (`xlib/xhttp_1_0_0.py`, epi `2X0B2XW`, 22 308 bytes) and **`1_0_1` 2026-10-19** (`xlib/xhttp_1_0_1.py`, epi `VC9QWYY`, 22 966 bytes) — the first entry in this repo citing its release ticket, as the convention asks. Verified before it was committed: xlint-clean, **223 tests green against it** through a shim package (the suite has since grown to **239**; the 6 that fail are `ContentNegotiationTest` — xhttp gzips regardless of `Accept-Encoding`, the known defect behind `#143` and `BFNRBG7`), and the live-socket smoke test returning the same responses as the source. **Running in Space-Traveller's game server and behaving, per the human** — which answers the "validate against real code" condition by use rather than by a campaign; the released artefact survives that use (`#117` done 2026-10-18). **The nineteen `err_*` lines are the reason the released file can be told apart from python**, and the reasoning behind them is now in `dev/xhttp/SPEC.md`. **The refresh flakiness is closed — the human's report, 2026-10-19: the flakiness is fixed, and both servers are now on `xhttp_1_0_1`.** That is the second version, and it is the fixed one: it carries the crucial fixes — multiple requests per connection, and the signalling when a connection is about to be closed. Both verified in the artifact itself (`xlib/xhttp_1_0_1.py`: `_server__serve_forever(...,max_requests=120)` and the `connection: close` header). **An earlier note here said `1_0_2` and read the missing `1_0_2` as a release that had not been made; both halves of that were wrong** — there is no `1_0_2` because the second version is `1_0_1` (the human's correction, 2026-10-19). **What 1_0_1 does not carry** is the `HTTPDoubleDotForbidden` → 400 branch and the removal of the redundant second `client.close()` in the 505 branch, both on master as `dd58524` (`AC9YJYQ`). The first of those is the only pending xhttp defect that would produce a *sometimes-failing page* — in 1_0_1 that exception falls through to the blanket handler, which prints a traceback and answers **500** — and it is reachable because 1_0_1 moved the `..` guard behind percent-decoding, so the guard now reads the decoded path. **So the next release wants `dd58524`; the release is the human's call.** **Moved in from Space-Traveller 2026-10-10**; `xlib_dev` load fixed (#116). **Suite: 239 tests, 6 failures, 1 skipped** as of 2026-10-19 — the 6 are `ContentNegotiationTest` (`dev/xhttp/test/test_response.py:282`): xhttp gzips regardless of `Accept-Encoding`, which `VERSIONS.md` 1_0_1 records as ruled an issue and not yet fixed. **They had no ticket until 2026-10-19** — `AC9YJYQ` claimed they "are filed separately" and they were not, checked by listing every open ticket rather than by searching a keyword. Now `BFNRBG7`, taskview `#143`. The two failures this row carried since 2026-10-12 were **not a defect in `websocket.send`**: `_/websocket.py:62-65` validates correctly, and both tests had `pass` inside their `assertRaises` with the comment *"Correct implementation would raise here"* — they had never been written. `7Z7DE78` argued the opposite at length and was wrong; the tests now call `send`, and the suite is green against **both the source and the bundle**. Earlier in the row's life: was 19 errors until the file-serving tests were corrected from tuple config to the dict shape `_/response.py` actually reads. Root is now clean: docs, `xhttp.py`, `_/`, `test/`, and `compare/` for the temporary RFC comparison material (`ba84849`, #124), plus `REVIEW.md` and `TODO.md` (`0a0dcd8`, #118). `95d700b` relocated the 60s-timeout fix into `handshake()`; it does not regress it and closes none of `Z70VRAC`'s five faults. **Validated against real code in Space-Traveller** — the game server has been running on xhttp and the released artefact survives that use (`#117` done). **The root file now reflects the error classes (2026-10-17, uncommitted)** — nineteen `err_X = err.X` lines at `xhttp.py:62-80`, added so a caller of a *bundle* can still name them (see *Blocked* (a)). Bundled, they come out as `err_HTTPError = _err__HTTPError`; the suite still runs 223 with the same 2 failures. | `dev/xhttp/`, `dev/xhttp/SPEC.md` |
| **modelbench** | — | Under active work (commits 2026-09-28/29 replaced the results catalogue with `ledger.py`); two questions left | `tools/modelbench/`, taskview #61, #63 |
| **epiq boards** | secretary | XLib **54 tickets — 37 in Todo, 4 in progress, 13 in Done**, counted 2026-10-21 (the count was 43 before that session; **`0AFZHPW` was the new one then, and `PNAJ6D0` since** — bbprs stops hardcoding one user's account, workspace and repos). **The In progress lane holds `9FJ358V`** (the epiq sync rule — part of it merged as `c7f9269`, the divergence report still open), `NAHEGJE` (marduk) and `AC9YJYQ` (xhttp collect); the Done lane holds **`62624K9`** (the xlint watch reload, merged 2026-10-21) and **`9Y4VV1M`** (the commit hook's diagnosis, merged 2026-10-21). **The In progress lane was empty on 2026-10-18 and is not now**: `NAHEGJE` (marduk), `AC9YJYQ` (xhttp collect) and **`K93Z39B`** (the `news` command — **reopened 2026-10-20, because PR #47's repair did not hold in the topology this machine actually runs; PR #50 is the fix**). The Done lane holds `SNXBR23`, `A7DGZYZ`, `TAQ74SC`, `48GH7NW`, `XP56NNC`, `YFJZRYC`, `MY4ZS5D`, `DW94JXN`, `PHF9QZQ`, `2X3PZT3`, **`VTJVHMY`** (the skynet window bounds, 2026-10-20 — **Done means the agent finished it; the merge still waits for the human's review**), **`QPDJ8RF`** (the test-layout guard, merged 2026-10-21) and **`PNAJ6D0`** (bbprs takes its account, workspace and repos from configuration, merged 2026-10-21 as `c38e23b`). **Fourteen tickets closed on this board without being merged**, in one session: seven whose commits are on master (`ZRTSZMB`, `7Z7DE78`, `NJ529TQ`, `GADE1PY`, `W06YDEQ`, `2X0B2XW`, `VC9QWYY`), four pybundle tickets closed as ruled-and-landed or verified (`F7KHKM8`, `S1G5037`, `EZAVYNM`, `YEBP3QB`), **`R9H4PVD` closed as superseded rather than executed** — its repair would now reintroduce the error it was written to prevent — and two filed from the Traveller run (`86CDJV2`, `JD9DWVN`). **Every one was verified against the tree, not against the ticket's own account of itself**; that check is what separated the fourteen from four that only looked closable. An empty In progress lane is a reading, not a fact about the work: the work is happening on a branch, which the lane does not track. The 2026-09-30 reshuffle put every ticket on the board of the repo its change lands in; this repo also carries a readonly `Closed` archive board | both boards |
| **pybundle acceptance** | secretary | **PASSES 2026-10-21: the bundled Traveller runs, and is byte-identical to the unbundled one.** 143 files, ~10 600 lines in, 400 KB out; parses and compiles clean; **332 diagnostics, all R1.6 "a second reference is dropped"**, none an error; **zero indentation warnings** on a real tab-indented project, which is D23's calibration measured outside XLib. **The bundle is xlint-clean**, which D32 requires of it — it was not, until the double-blank defect was fixed. **Measured against the unbundled server on the same tree: the startup output is byte-identical across 86 lines, and five HTTP requests return byte-identical responses, status codes and lengths.** **Five defects came out of the run, and every one of them produced a bundle that compiled clean and then failed** — the shape a text-level test cannot see: `JD9DWVN` (a module reached through a package attribute reached the package's globals — 141 names, one `NameError` each; **the ruling is alias**, ruled by the human), `VQKH390` (a name after a dot renamed when the base was a module alias), `RX5H4P3` (a def's own parameter renamed while the body's use of it was not), `14VP9PT` (**the bundler tracked indent blocks where python tracks scopes** — a name assigned in a nested block was not the function's own, and a class body's names shadowed the methods defined in it), `86CDJV2` (a removed import that was the file's last statement left a blank behind). **Six commits on `fix/JD9DWVN-bundle-traveller`, PR #76, one per ticket ref, plus the spec's D38–D43. Nine new tests in `tools/pybundle/test/test_acceptance.py`, in xtest's idiom, each checked to fail against the code before its fix.** **The artefact is not committed** — 400 KB of generated code, and it belongs to the run rather than to the repository. | `Space-Traveller/server.py`, epiq `86CDJV2`, `JD9DWVN`, `VQKH390`, `RX5H4P3`, `14VP9PT`, PR #76 |
| **xlint: html rules** | secretary | **IMPLEMENTED AND MERGED 2026-10-19 — PR #42, on master as `5c1865e`.** The three rules as ruled: **unclosed tags (strict)**, **closing tags that shouldn't be** (void closer, stray closer, mis-nesting) and **bad indentation** (depth mismatch + spaces-not-tabs, depth in the file's own unit). **Code in `tools/xlint/_html.py`** — a tokenizer, one walk over the tags, the depth rule — imported by `xlint.py`; `.html` in `_ALL_SUFFIXES`; a `--no-html-*` flag family (7 flags). **23 new tests; the suite is 90 green.** **Measured on Traveller's 27 html files + Mallesne's: unclosed 0, stray 0, depth 774 — 589 the one systematic off-by-one, and the single -1 is `main.html:134` as the earlier measurement said** (it said 773/588; the one-finding difference is a detail of a script that was never kept). **Trailing whitespace reads 7 under xlint's own generic rule, not the 3 that script found — the difference is four lines ending in a tab.** The rules are stated in `doc/style/html.md`. **The human merged it on their own instruction so they could run it over Traveller** — `xlint` over Space-Traveller's `html/` folder gives 783 findings (774 depth, 7 trailing whitespace, 2 double blank), and Mallesne's one html file is clean | epiq `YFJZRYC`, taskview `#139` |
| **xlint: the worktree blind spot** | secretary | **FIXED 2026-10-19 — PR #44, merged as `36b20c5`, two tickets: `XP56NNC` (the linter) and `2X3PZT3` (the hooks).** The linter excluded every file in a `.work/` worktree and said `clean`; the hook that runs it never ran in a worktree at all, so the style gate and the ticket-ref check were both open there. Both fixed, both measured; the gate's output at the repository root is unchanged. | epiq `XP56NNC`, `2X3PZT3`, taskview `#144` |
| **xlint: the watch never reloaded the rules** | secretary | **MERGED 2026-10-21 — PR #68, on master as `dd2f27b`, by rebase, on the human's authorisation.** The watch read `.xlintignore` once, at startup, and kept it for the life of the process, so a rule edited mid-session changed nothing until the tool was restarted — and restarting is the workaround watch mode exists to avoid. **Not only a reload**: the inotify watch set was built once from the same stale rules, so a directory excluded at startup had no watch at all, and re-reading the file would not have produced events from it. **The rules are now part of what is watched** — an ignore file edited, added or removed is noticed; the watch set is rebuilt over the new scope in both directions; a rules change re-reads the whole scope and redraws silently, so a newly ignored file leaves the report and a newly un-ignored one enters it. **The other half of the ticket**: `main()` built the rules from `args.paths[0]` alone, so a run over two repositories was governed by the first one's chain — each path is now governed by its own, and the deepest watched path wins for a file under two of them. **13 new tests, all 13 failing against the old code**, and mutation-checked. | epiq `62624K9` (Done), taskview `#121` |
| **the epiq sync rule** | secretary | **MERGED 2026-10-21 — PR #69, on master as `c7f9269`**, on the human's instruction: *"There should be a rule of doing an extra epiq sync. Add one if there isn't. Perhaps make the tool say explicitly that another sync is needed."* **The rule is now written down** — `doc/epiq-workflow.md` has a **"Sync twice"** section: the first `epiq_sync` after a write can return `skipped: true` with the events still only in the actor's pending log, because the pending log has to be finalised before it is flushed into the committed log and the flush is what commits it. Measured twice on 2026-10-20. **The rule: write, sync, check, sync again while the check says so.** `AGENTS.md` names it in the pointer table, so a change to it is announced by `news`. **The tool says it too** — `epiq-pending.py` reported "8 events in flight, not yet synced" and stopped there, which reads like a status rather than an instruction; it now says *"these writes are not durable: run epiq_sync again until this line is gone"*, and only when something is in flight. **The rest of `9FJ358V` is still open**: naming the ticket for stranded referencing events, and the divergence report. | epiq `9FJ358V` (In progress), taskview — |
| **the commit hook's diagnosis** | secretary | **MERGED 2026-10-21 — PR #71, on master as `b05f330`**, on the human's instruction (*"Do 9Y4VV1M too, since it's so similar"*). A freshly filed ticket lands in the actor's `~pending` log, so `validate-ticket-ref.py` could not find its ref and refused the commit with **"Invalid ticket ref"** — true, and useless: the ticket exists, it had just not been synced. **It now says that**: *"was filed but not yet synced"*, with the instruction to run `epiq_sync` and again if it reports skipped. **The ref is still refused** — this is the ticket's option 3, not its option 2: a ref nobody else can resolve should not pass a gate whose whole job is to check that it resolves. **One line of dead code went with it** — the loop tested `.endswith(".backup")` inside a `glob("*.jsonl")`, and that glob never matches a `.jsonl.backup`, so the check could not run; the mutation check is what found it. **Six tests, the validator's first.** | epiq `9Y4VV1M` (Done), taskview `#174` |
| **changing a hook does not change the hook that runs** | secretary | **SUPERSEDED 2026-10-21 — the hooks are symlinked now, so the problem is gone rather than documented.** `tools/hooks/install.sh` **copies** the hooks into the shared git directory, so the running hook is the copy and a merged hook fix is **inert on the machine** until it is re-installed. **Measured**: `b05f330` was merged and the live hook compared against the source immediately afterwards was still the old one — the fix was on master and the hook that gated every commit was not. **The same shape as a record quoting a live thing and being stale** — and the third time in two days it has cost something. `W4QP4GK` wrote the rule down; **`PZH78FS` then made it unnecessary**: the hooks are **symlinked**, so a change is live at once and there is no install step to forget. **The guard**: `pre-commit` is a regular file that checks every link resolves and fails loudly if one does not — a dangling link is a **silently absent gate**, and git says nothing at all about it. | epiq `W4QP4GK` (Done), `PZH78FS` (Done) |
| **the hooks are symlinked, and one of them is the guard** | secretary | **MERGED 2026-10-21 — `PZH78FS`, commit `e7ff041`**, on the human's instruction (*"would it be practical for the hook install script to just use a symlink instead of copying anything?"*). **A change to a hook is live at once**, and the whole class of problem the last row records is gone rather than documented. **Measured before writing it**: git runs a symlinked hook; in a worktree it runs and `2X3PZT3` is unaffected; after **moving** the repository it still runs, **because the link is relative**; editing the source takes effect with no install step; no hook resolves its own location; and `install.sh` was **already symlink-aware**. **The cost, and the guard**: a dangling link is a **silently absent gate** — git accepted a commit with the source deleted and printed nothing at all, not even the hint it gives for a non-executable hook. So **`pre-commit` is a regular file and is the guard**: it verifies every link resolves, fails loudly with the fix if one does not, and then runs the style gate itself. **Three details the measurements decided**: the link is relative where the shared git dir is the repository's own `.git` (a relative link survives a move, an absolute one does not); the **source** is made executable rather than the link (a link takes its target's mode); and the installer **removes stale links** for sources that are deliberately gone. **Verified live** on this machine, both directions. | epiq `PZH78FS` (Done) |
| **xtest: the repository's runner** | secretary | **MERGED 2026-10-20 — PR #52, four commits, merged as `df34b07` on the human's authorisation.** **One command runs the repository's tests: `python3 tools/run_tests.py` — 934 tests, 14 suites.** The 6 failures are the known `ContentNegotiationTest` (epi `BFNRBG7`). **Five suites were inert** — `tools/test/test_epiq_pending.py`, `dev/xconf`, `dev/xschema` and xtest's own two — each exiting 0 having run nothing, and 67 tests that no command could run. **xtest grew to carry the runner rather than the suites being rewritten**: it now runs `unittest.TestCase` classes through unittest's own machinery, so the 852 unittest tests run under it and keep their `addCleanup`, `subTest` and skip decorators. A file runs that file alone; a module's fixtures wrap that module's tests; `import xtest` works from any directory; every assertion takes a message. **Two stale tests found and fixed**: `xlib_dev`'s library list had not been updated since `xhttp` joined `dev/` on 2026-10-10, and `dev/xschema`'s suite imported the *released* xtest rather than the development one. **Not released** — `dev/xtest/VERSIONS.md` still reads 1_0_0, and a release is the human's call | epiq `A7DGZYZ`, taskview `#155` |
| **xlint: the absolute-path check on Python files** | secretary | **MERGED 2026-10-20 — PR #52, merged as `df34b07`.** The check existed and ran in the Markdown branch only, so `tools/tool_schema_cache.py:14` carried this machine's path and the linter said nothing — the finding `STATUS.md` left open on 2026-10-20, when the drift sweep found the ticket closed and the check not covering the file the finding was about. **Two decisions:** **`~/` is not flagged** (the rule is about *one machine's* layout, and `~/` is the portable form — flagging it would have meant rewriting twenty-odd correct lines), and **a docstring is not a string literal** (a docstring names a location; a string literal is a value, and one that looks like a path is usually a fixture). Five tests, one of them end-to-end over every tracked `.py` file | epiq `7HP67R2` |
| **the category vocabulary** | secretary | **RULED and APPLIED 2026-10-20 — PR #52, merged as `df34b07`.** Thirteen categories, down from eighteen, all lowercase with no dash or space. `XLib` → `xlib`, with `pybundle` and `xhttp` folded into it and their part as the second level — the tag; `Agents` and `agents` → `agents`; and `dev` and `testcat` left the vocabulary (one cancelled scratch task each). **XLib work that is not about any particular library or tool there gets one word, `xlib`**, rather than a new word per task — that is what stops the vocabulary expanding again. 130 appended rows in the store (append-only, last-row-wins); four panels filter on those names and all four are updated | epiq `SNXBR23` |
| **xtest 1_1_0 — released** | secretary | **RELEASED 2026-10-20 — PR #55, on master as `e8ffe49`** (epi `48GH7NW`, Done). **Verified against the release rather than the source:** `from xlib import xtest` resolves to `xlib/xtest_1_1_0.py`, and that file runs xtest's own suite — 13 passed. The release gate ran this repository's own xlint over the bundle and it is clean. **The decision the release carries, written into `AGENTS.md`, `doc/development.md` and `dev/xtest/SPEC.md`:** *rewrite to xtest if it gets in the way*, and *always write new tests with xtest* — the human's ruling, *"standardize on xtest means eventually using only xtest. Avoiding a full rewrite is reasonable, but the decision should be tagged … so the dogfooding works and won't turn into two parallel systems."* The two names are also epiq tags on `QJEA7EM` and `48GH7NW`, so the decision is findable by tag | epiq `48GH7NW`, `QJEA7EM`, taskview `#155` |
| **skynet: the window bounds** | secretary | **MERGED 2026-10-20 — PR #58 on master as `57d4e37`, PR #59 as `97d62e2`, both on the human's authorisation** (*"you can merge the changes, so I can test them myself"*). Board epiq `VTJVHMY` (Done), taskview `#158` (done). The cap comes from the space available — the terminal's own height, which in a tmux pane is the pane — and the six lines spoken for before a model is shown leave the rest, split evenly between the two sections **with the odd line to Today** (the human's ruling, 2026-10-20). A section with more to show spends one line of its allowance on the note, so a table with *n* lines of room shows *n − 1* models and one line of `… +N more`. **Measured**: the display fits every pane height from 1 to 49 lines, checked through a pty at each height; at 30 lines it is exactly 30. The suite is 26 tests, 19 of them new, in xtest's idiom; `xlint` is clean. **The human's review, 2026-10-20, in two parts**: the blank after the `Skynet` header is out (*"the current version of skynet doesn't have that empty line, so it's not necessary"*), and the section title moved into the header row to carry the column labels (*"dropping the 'Model' header in both tables and replacing it with the previous line's contents"*) — so each table shows **one more model** than before the review. The floor, where a pane is too short for the two sections, is six lines, and it gets the counts on one line (*"makes sense"*). **The watch loop now watches the terminal's size as well as the database's** — a resized pane has to redraw, or the old layout stays and overflows. | epiq `VTJVHMY`, taskview `#158`, PR #58, PR #59 |
| **the repository's own guard over its test layout** | secretary | **MERGED 2026-10-21 — PR #77, on master as `b1dd369`**, on the human's authorisation, and without review because the change breaks nothing. `tools/run_tests.py`'s `SUITES` did not list `tools/modelbench/test`, so eight modelbench test files were unreachable and **the guard over the test layout was red** — the failure the guard exists for, reported by the guard itself. **The fix is the one line the guard asked for, and the guard immediately found a second defect it had been hiding**: two of the eight had no `__main__` block, so running either on its own imported it and **exited 0 having run nothing** — *"a suite that cannot be run by the obvious command is worse than one that fails loudly: it reports success over content it never examined"*, in the guard's own words. **The ticket's own premise, "the eight pass on their own", was true and misleading**: seven ran, and the two that did not also reported success. Measured in the worktree: `tools/modelbench/test` 81 passed, 0 failed; `tools/test` 62 passed 1 failed → **63 passed, 0 failed**; **14 suites passed, 1 failed** — the one remaining failure is the known `ContentNegotiationTest` six. The suite was checked for hermeticity before the merge — no absolute paths, no home references, no network | epiq `QPDJ8RF` (Done), taskview `#179` |
| **the coordination mechanism** | secretary | **RULED AND LANDED 2026-10-21 — the file-claim system is retired, and the per-person state files are written by the secretary at merge time.** PR #79, on master as `54e9621`. **The audit is `doc/audits/2026-10-21-claim-system.md`** (commit `3497f7b`), and it is measured rather than read off the ticket: **nothing checked a claim at commit time** — the pre-commit hook runs xlint, the pre-push hook validates ticket refs, neither reads `claims.json`; and **the claim key was the path, which differs per worktree**, so one source file had two claim keys in two disjoint claim stores and the conflict check could not fire, while two of the three live worktrees had no `.agents/` at all. **What went:** `claim`, `release`, `release-all` and `status` — nothing in the repository called them. **What stayed:** `check-clean`, because it reads the **working tree**, so it needs no shared state and sees across worktrees. **What replaced it:** a worktree per ticket is the boundary, and **a Done ticket does not carry `STATUS.md`, `TASKS.md` or `HISTORY.md`** — the secretary writes them at merge time, which takes the file every session writes out of every branch's diff. **Seven new tests**, each checked to fail against the old code. **The loss is named:** there is no longer a way to ask who holds what. | epiq `5S8FY10` (Done), taskview `#184`, `doc/audits/2026-10-21-claim-system.md` |
| **xAudit tool** | — | Decided, not started | `doc/plans/xaudit.md` |
| **taskview periodic time refresh** | — | Planned only | `doc/plans/taskview-time-refresh.md` |

### Merging

The human's decision of 2026-09-30: every piece of work goes on its own
feature branch, one commit per ticket, ref-prefixed, and **nothing merges
before the human reviews it**. Agents move finished tickets to Done themselves;
after the human has approved a ticket an agent may merge it to master, delete
the branch, and close the ticket (epiq `H2NC2A2`).

**No pull request is open.** PR #50 (`K93Z39B`, the `news` command's workspace resolution) was
merged on 2026-10-20 as `f12ebd5` — 36 tests and 11 mutations killed — and this
line said it was still waiting for the human, which it had not been since the
previous day. **PR #78** (`PNAJ6D0`, **bbprs stopped hardcoding one user's
account, workspace and repos**) was merged on 2026-10-21 as `c38e23b` — by
rebase, on the human's own instruction (*"Rebase-merge it."*) — **and the
branch and worktree are deleted**. **PR #68** (`62624K9`, `xlint --watch` never reloaded
`.xlintignore`) and **PR #69** (`9FJ358V`, the epiq sync rule) were both merged
on 2026-10-21 — by rebase, on the human's authorisation for the first and on the
human's own instruction for the second — as `dd2f27b` and `c7f9269`, both
branches and worktrees deleted. PR #33 (`ZRTSZMB`) was merged on 2026-10-18 — rebase, branch
deleted, `dc078ce` — and with it the seven Done-lane tickets whose commits are on
master are closed: `ZRTSZMB`, `7Z7DE78`, `NJ529TQ`, `GADE1PY`, `W06YDEQ`, `2X0B2XW`,
`VC9QWYY`. Each got a `Solution:` comment first; the four that only had a
prose outcome comment got one carrying the commit hashes, since
`^Solution:` is what finds a resolved ticket on the board. The 2026-10-02 run held
six and merged them as a flat
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

### pybundle — three specifications, and nothing marking which is current

**The bundler is in the tree** (re-measured 2026-10-20): six modules,
`bundler.py`, `bundler_cli.py`, `bundler_imports.py`, `bundler_names.py`,
`bundler_source.py` and the entry file, all tracked, with **203 tests in six
files under `tools/pybundle/test/` — all green**, and a clean working tree.
**What was deleted on 2026-10-14 (`5e87ae8`, epiq `055TS78`) was the *old*
five-phase implementation** (`bundler.py` + `bundler_impl.py`) and its seven
fixtures; the rewrite landed on 2026-10-17 and replaced it. A line here said
"there is no bundler in the tree" and was right for four days and wrong for the
rest. **What is still true is the part about the documents**: a reader arriving
at `tools/pybundle/` sees **three specifications with nothing marking which is
current**:

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
- `tools/pybundle/_/` is an empty directory left behind. Git does not track
	empty directories, so `_/` exists on disk and not in the repository.
	**The test folder is no longer in that state** (corrected 2026-10-20): it
	held the 65 tests of `608621e`, then 138 in five files, and now holds
	**203 in six files, all tracked and all committed** — pass 3 re-derived
	against the alias ruling, plus the shim and structure work. The line that
	said "two files untracked and three more modified" described 2026-10-15.

## Blocked / needs attention

- **The secretary switched XLib's working tree onto a stray branch named `other`
	this session, minutes before shutdown — caused, caught and reverted.** Two
	`shell` calls issued in one block raced: the first began `rm -rf
	/tmp/opencode/co-probe`, the second's `cd /tmp/opencode/co-probe 2>/dev/null
	|| true` lost the race and its `|| true` swallowed the failure, so
	`git switch -c other` ran **in the repo** and left `?? f.txt` behind.
	Reverted with `git switch master`, `rm f.txt`, `git branch -d other` (at
	`3ebc520`, identical to master, `-d` not `-D` so the delete would have
	refused otherwise). **All seven modified files intact**, including another
	agent's `dev/xhttp` work. **Nothing was lost because the command was `git
	switch`** — it carried the uncommitted changes across. Recorded because the
	human should know their repo was briefly on a branch that does not belong to
	them, and because the near-miss is the clearest possible demonstration of why
	`checkout` is the banned one.
- **`agent-coord.py news` destroyed every agent's claims, and the rule changes
	it exists to announce never arrived. Both halves are fixed and on master:
	PR #47, commits `36554c9` and `806253e`, for the claims-wipe, and PR #50,
	merged 2026-10-20 as `f12ebd5`, for the workspace resolution. #142
	(reopened), and `8FVW49J` for the guard beside it.**
	The four breaks and what they measure are in the Snapshot above. **What PR
	#47 did not fix is the first break.** The repair settled on the opencode
	client by walking this process's ancestry and assumed the client is an
	ancestor of the tool shell; under opencode 2 it is not, so the walk finds
	the shared service, whose cwd is the home directory, and the session
	resolves to `/home/xonok` again — measured live on 2026-10-20, with `news`
	printing `no rule files found in /home/xonok — nothing checked`. **So the
	rule changes still do not arrive for a session of this shape, and the
	`git checkout` ban is one of them.** PR #50 finds the client by what it says
	about itself — the session id in its own arguments, and the directory it
	works in — and the service is never a candidate. **MERGED 2026-10-20 as `f12ebd5`, on the
	human's authorisation.**
	**The stale identity is handled rather than left to rot:** the service's pid
	was the session key, so every session attached to the service was given one
	identity, one notes file, one rule cursor and one set of claims. With the
	key changed, that identity is a leftover whose claims are stranded where the
	guard refuses the rightful owner. **It is now taken over once, with its
	claims and its cursor, and re-tagged to the workspace the session is really
	in** — the old tag was the home directory's name, which was never a
	workspace. Measured on the live state: `ids.json` holds one entry,
	`pid-1252` → `XLib/secretary-1`, and the claims are under it.
	**`$HOME/.agents/` still exists**, and a session whose window was opened in
	the home directory resolves there, which is correct for that window and not
	something to delete from outside the repo. → `tools/agent-coord.py`,
	taskview `#142` and `#145`

- **Three bundler tickets are now closed, and one of them was closed for a reason
	that reads as done and is not.** Closed 2026-10-18: `F7KHKM8` (all three
	name-import shapes ruled and landed as D20/D24), `S1G5037` (both halves of the
	indentation ruling landed, `_warn_indentation` at `bundler.py:163`),
	`EZAVYNM` (all five spec edits written, D22 and D25), `YEBP3QB` (the file-like
	sink requirement, verified byte-identical across stdout, file, `StringIO` and a
	real pipe, and the bundler closes nothing it did not open), and **`R9H4PVD` —
	closed as superseded, not executed**. Its repair removes the rebinding language
	from D9 and D19, and the 2026-10-15 alias ruling reversed F13, so that language
	is correct again and executing the ticket would now *introduce* the error it was
	written to prevent. D20/D24 restate it and the supersedes table at
	`SPEC.md:747` carries the correction. **A closing is a claim about work, so it
	needs a check that could fail** — here the check was asking what happens if the
	ticket is executed, and the answer was that it breaks something.
- **`6MFX0Z1` stays open, and the acceptance test now passes.** The rewrite
	landed (12 commits, 203 tests) and the bundler's structural machinery held
	up on a 143-file foreign codebase; **the defects the run found were in
	emission rules and in the scope model, not in the design**, and all five
	are fixed and in `PR #76`. What is left is the housekeeping — **`SPEC_new.md`
	is still in `tools/pybundle/` beside `SPEC.md` and `SPEC_old.md` with nothing
	marking which is current** (taskview `#183`) — and the shim option
	(`AYB2896`, future work). The ruling `JD9DWVN` asked for is **alias**,
	ruled by the human on 2026-10-21. See *pybundle acceptance* above.
- **Marduk tracks the kitty window, not the opencode process** — found and filed
	2026-10-18, epiq `NAHEGJE`, task **#136**. `tools/oc-agent:114` records its own
	`$$` as the registry entry's `pid`, and that process is the launcher script,
	a child of the window's shell — so `read_registry` reaps on the tab. Verified
	live: every registry `pid` resolves to `/bin/bash oc-agent secretary`, whose
	child is the `opencode --session …` TUI. **The human corrected their own
	earlier spec** ("keep it open as long as the window stays open") — the window
	is kitty, the session is the opencode process. Three decisions taken the same
	day: record the opencode child's pid, keep service-only sessions (those the
	service reports running that no oc-agent launched, including a secretary's own
	session) shown on the service's word alone, and fold in two leaks found beside
	it — an entry whose `pid` is not an int is never reaped, and a recycled pid is
	indistinguishable from the original. **Implementation must be checked by
	launching a real window**: backgrounding the TUI is safe only without `set -m`,
	or job control puts it in a background process group and the first tty read
	raises `SIGTTIN`. **The terminal is herdr now (2026-10-21), and the
	distinction holds unchanged** — herdr's pane is the window, the opencode
	process is the session — and **herdr's own integration now reports the pane's
	session id by a second, independent route** (`agent_session.source =
	"herdr:opencode"`), which is the fact `NAHEGJE` is about, measured live.
- **Marduk shows the wrong session for a window that has been `/new`ed, and two
	lines for it while the new session is busy** — the human's report 2026-10-21
	(*"the panel shows 3 unnumbered secretaries among the number ones… the
	unnumbered ones are essentially secretary-1, so it doesn't make sense for
	there to be 3 of them"*), filed as epiq `0AFZHPW` (XLib) and `M9J6F8W`
	(Agents), task **#173**. **The human's decision, 2026-10-21**: *"the result
	must be some kind of process that represents the specific opencode instance,
	even if the backend is the same… when a new session appears, it should be
	possible to determine whether it's in the same opencode instance (not the
	kitty or herd window, but the opencode process within it)."* **So the
	identity is the opencode process and the link comes from the process
	itself — and the mechanism for it exists and is proved.** A local plugin
	with a **`tui` entrypoint runs inside the opencode TUI process** (a local
	plugin is a directory under `~/.config/opencode/plugins/`, and its
	entrypoints are resolved by name inside it — `server.ts` for the service,
	`tui.ts` for the TUI), and `ctx.ui.router.current()` is the session the
	window is on. **Measured against the registry, live: three of the four
	windows were showing the wrong session** — only the one that had never been
	`/new`ed was right. The Space-Traveller window is the case the panel hides
	best: its live session has been idle for hours, so it is not in
	`/api/session/active`, so the panel shows its **dead launch session** — which
	is what *"secretary-2 idle⚠ 14h15m"* is. **Four windows were open** (oc-agent
	slots 1–4, all four registry pids alive) and the panel showed **six lines,
	three of them named `secretary`** — so the panel was wrong in two ways at
	once, and the wrongness is not marduk's alone. **First, the registry names a
	session while the durable thing is a window.** `~/.opencode/agents/<sessionID>.json`
	is written once at launch (`tools/oc-agent:140-150`) and never updated; a
	`/new` replaces the window's session and the entry keeps naming the old one.
	Measured on the live machine: the XLib slot-3 window had been `/new`ed at
	18:06 and again at 22:22, so its entry was stale by two `/new`s, and the
	Agents slot-1 window three times. **The second failure is worse than the
	extra line**: marduk shows service sessions only while they are *active*,
	so when the new session goes idle it drops off the panel and **the dead
	launch session is shown in its place** — the window is still listed, for
	ever, under a session it left hours ago. **Second, the live session loses
	its slot number.** `tools/oc-agent:112-116` gives the session it creates the
	title `secretary-3`; a `/new` session is created by the TUI with **no
	title**, and `~/.config/opencode/plugins/agent-title.ts` renames any session
	that still carries a default title to the **agent name** (`renameOnce`,
	`agent-title.ts:91-114`). **Proven, not inferred**: a session created through
	the API with `agent:"secretary"` and no title had `title=None`, and after one
	model call — the plugin's `context` hook — its title was `"secretary"`; a
	fresh TUI session gave `title=None, agent='build'`, so the server does not
	name sessions and the plugin does. **Two facts that shape the fix, both
	measured.** The service exposes **no process↔session link** — `/api/session/active`
	is documented as the sessions owned by *the service* process, the `session`
	table has no pid, `event_sequence.owner_id` is null, and the plugin's
	`session.hook("context")` carries sessionID and agent only, so **nothing
	outside the opencode process knows which session a given window is on**. And
	the **plugin that names every session is in no repository** — `~/.config/opencode`
	is not a git repo, and the only other copy on the machine is a v1-era backup;
	every session name on the sidebar and on the panel comes from it. **The fork
	is settled — by the human's own ruling, and the third option is the one that
	works:** the process reports its own session, keyed by pid, and marduk joins
	that against the registry's pid. **The proof, live, on every opencode process
	on this machine:**

| pid | slot | role | workspace | registry names | the process is on |
|---|---|---|---|---|---|
| 26248 | 4 | secretary-4 | XLib | `ses_ea320750…` | `ses_ea320750…` same |
| 4370 | 1 | secretary | Agents | `ses_ea6ba68d…` | `ses_ea2e5a47…` **different** |
| 10116 | 3 | secretary-3 | XLib | `ses_ea6d8376…` | `ses_ea53c242…` **different** |
| 23231 | 2 | secretary-2 | Space-Traveller | `ses_ea784d83…` | `ses_ea611963…` **different** |

	**Three of the four windows were showing the wrong session, and only the one
	that had never been `/new`ed was right.** The implementation is three pieces
	and is written out in full on `0AFZHPW`: a TUI plugin writing
	`~/.opencode/instances/<pid>.json` (`{pid, cwd, sessionID, role, at}`, with
	`sessionID` **null while the window is on no session** — the honest answer
	between a `/new` and the first message of the new one); marduk's join, which
	changes the first step of `_collect()` so that each registry entry names the
	session **its pid reports** rather than the one recorded at launch, with the
	entry's role and workspace staying with the window; and the launcher half,
	which is a comment on `GY2AVQD` (the session title is a fourth surface the
	allocator's name has to be rendered on, and the join is by pid but the panel
	still needs a *name* for each window). **Two things an implementer should
	not re-learn:** the TUI plugin's export is **`Plugin.define`** — a named
	`define` import fails and is **silently ignored**, so the TUI looks fine and
	the plugin never runs — and `ctx.ui.tabs.enabled()` is **false** here
	(`cli.json` has `"tabs": {"mode": "off"}`), so the session comes from
	`ctx.ui.router.current()`, not from the tabs. **The human authorised the
	secretary to build it (2026-10-21), and it is built: PR #73**, branch
	`fix/0AFZHPW-window-session`, on master as `42e137f`. The reporter is
	`tools/marduk/plugin/instance-report/tui.ts` — **tracked in this
	repository**, and the launcher links it into `~/.config/opencode/plugins/`
	the way `agent` is linked into the Agents workspace, so every machine gets
	the same one. marduk joins the registry to the reports by pid: a registry
	entry names the session **its process reports**, not the one recorded at
	launch, so the session a window left behind drops off the panel and the
	window appears once, under its own name; a window on no session at all is
	filed under a key of its own. **11 new tests in
	`tools/marduk/test/test_instance.py` (xtest); the marduk suite is 111
	green.** **The live panel now shows four windows and four lines**, each on
	the session its process is on — measured before the change, three of the
	four were showing the wrong session. **Left out on purpose:** the *session
	title* after a `/new` still comes out as the bare agent name, which is the
	`agent-title` plugin's doing and lives in the human's own config directory
	— Agents board `M9J6F8W`. The panel no longer depends on it: a window's
	name on the panel comes from the registry, which knows the slot.
	**MERGED 2026-10-21 — PR #73, on master as `dbe6c13`**, on the human's
	authorisation ("you can do the merge"). The panel was restarted on the
	merged code and the plugin link now points at the root checkout
	(`~/.config/opencode/plugins/instance-report` →
	`tools/marduk/plugin/instance-report`), so both are permanent: a new window
	reports itself, and a panel restart keeps the join. **The panel shows four
	windows and four lines**, each on the session its process is on.
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
- **`tools/release/release.py` — both breaks it had are closed (corrected
	2026-10-20).** The dev-folder path bug was **fixed and committed**
	(`c657694`, epiq `1ZY2Q5Q`): it resolved `ROOT / <library>` while the
	folders moved under `dev/` in `da1d163` (2026-09-17). **The second break —
	"the script cannot release anything, because it imports the bundler at
	module scope (`release.py:8`) and the bundler was deleted in `5e87ae8`" — is
	also closed, because the bundler is back.** The rewrite landed 2026-10-17
	and `tools/pybundle/bundler.py` is in the tree again. **Measured
	2026-10-20: `release.py` imports cleanly, and `bundled(entry)` is there**
	(`release.py:51`) — the bridge the human ruled ("spec as written, bridge
	separately"), which is `main` over a `StringIO`, because `bundle(entry) ->
	str` is not among the spec's seven functions. All five libraries in `dev/`
	bundle, and every bundle is xlint-clean. Still unaddressed: the non-atomic
	write, `release()`'s return type and the tagging question. **The
	consequence that was stated here — "there is currently no way to look at a
	bundle without writing one" — no longer holds**, and the README's "never run
	this to check something" warning no longer has a dead answer. All six
	releases in `xlib/` predate the move and nothing tests the path.
- **The release gate landed 2026-10-18**: `release.py` runs this repository's
	own xlint over the bundle and **refuses before writing**, so nothing released
	here carries a finding. **The gate is the repository's, not the bundler's** —
	the human ruled both halves: *"The release script still has to require
	xlint-clean output. It's a release gate for this particular repository after
	all"* and, of the bundler, *"the bundler's rules are slightly more open
	because I want to see what happens if I bundle traveller at some point. If
	Traveller can survive the bundling, then it's very likely that the bundler's
	behaviour is correct overall."* So D36 stands (add none, pass through the
	rest) and D37 puts the stricter rule in `release.py`, where it cannot stop the
	Traveller experiment from being run. **Traveller is the bundler's acceptance
	test** — bigger than any fixture, since nobody wrote the tests for it. Recorded
	as `SPEC.md` D37 and as taskview `#137`; the gate has its own
	`tools/release/test/test_release.py` (7 tests), including the pair that only
	makes sense together: the bundler passes a pre-existing finding through, and the
	gate refuses it. **Verified against the real library**: re-releasing xhttp
	through the gated path produces a file byte-identical to the committed
	`xhttp_1_0_0.py`, so the gate does not perturb the artefact.
- **The pybundle rewrite has code: the bundler is implemented, and 212 of its 212
	tests pass** (203 before 2026-10-21, and the nine that came with the
	acceptance repair). Implementation is programmer work and the secretary does
	not do it; the human was told and overrode that, so the work happened here
	and the record says so. What that leaves behind is three things the human
	has not ruled on, and they are worth more than the green tests:
	**(a) RULED 2026-10-17 and IMPLEMENTED the same day: a relative import in the
	root is allowed, and `RELATIVE_IMPORT_IN_ROOT` is retired** (`SPEC.md` D30,
	taskview `#130` closed, `#132` done, epiq `NJ529TQ`).
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
	**The implementation landed 2026-10-17, out of lane on the human's
	authorisation to write code** — guard, exception class and its two uses gone;
	the four tests that pinned it rewritten, 188 → **202 tests**. **A bundled
	library cannot be tested by its own suite** — `test_response.py:25` and
	`test_websocket.py` import internals and D17 means a bundle has no module
	objects — so running all 223 needed a shim package; the human's answer is
	*"we'll probably have to add an option to the bundler for making these shims
	automatically. Future work"*, filed as `#133`.
	**(b) The release path works, as of 2026-10-17** — also out of lane, on the
	same authorisation. `release.py` called `bundler.bundle(entry)`, which the
	spec does not have; the human ruled *"spec as written, bridge separately"*, so
	`bundled(entry)` lives in `release.py` and is `main` over a `StringIO` — the
	whole adaptation. **Verified without releasing anything**: the bridge's text is
	byte-identical to the CLI's for all five libraries in `dev/`, and a redirected
	`release("xhttp","rev",False)` writes a 22 308-byte `xhttp_1_0_0.py` that is
	xlint-clean. `1ZY2Q5Q` and `#129` can close. **What is left between
	`dev/xhttp` and a file in `xlib/`:**
	1. **Nothing mechanical.** All five libraries bundle, and **every bundle is
		xlint-clean**: `xhttp` 583 lines, `xschema` 469, `xcsv` 415, `xconf` 119,
		`xtest` 95. `dev/xhttp/VERSIONS.md` now exists (`#135`).
	2. **A finding I did not expect, and fixed**: an indented non-local name
		import lost its indentation, so the bundle **did not parse**
		(`IndentationError`). D20's *"rewritten in place"* read as *rebuilt*;
		recorded as `SPEC.md` D34. A statement can be correct text and still be
		the wrong bundle — that one only failed at compile.
	3. **Two library suites verified end-to-end against their bundles**: xhttp's
		**223 tests, same 2 failures as the source** (needs the shim, `#133`), and
		xcsv's **18 tests green through the public API alone**. `xconf`, `xschema`
		and `xtest` bundle and lint clean, and their suites import and run against
		the bundles, but they are xtest-runner based and were not counted the way
		the other two were.
	4. **The human's own gate: validation against real code in Space-Traveller**
		(`#117`). **Re-scoped 2026-10-18: the game server has been running on xhttp
		"for a bit now and seems to be working fine"**, so the original framing is
		answered by use. **The checkpoint is passed** (`#117` done 2026-10-18): **the
		released artefact survives being used by Space-Traveller** — `xhttp_1_0_0.py`
		(epi `2X0B2XW`, released 2026-10-18, verified xlint-clean and 223-green through
		a shim). **One open bug, attributed to
		the frontend and not yet established**: flakiness around refresh, which the
		live server does not show when *both* frontend and game run `dumb_http`.
		The frontend still runs `dumb_http`; an agent is investigating, and the
		planned experiment is to move the frontend to xhttp and see whether that
		fixes it. **That attribution is the human's reading, not a measured
		finding** — recorded as such.
	5. ~~**Two red tests** (`7Z7DE78`, `websocket.send` type validation).~~ **Gone —
		they were never real.** `_/websocket.py:62-65` validates correctly; the two
		tests were `pass` inside `assertRaises`, with the comment *"Correct
		implementation would raise here"*. Written properly on 2026-10-18, the suite
		is **223 tests green against the source and against the bundle**.
	6. **`#115` is unimplemented**, so the one gate that belongs in the release
		path itself — refusing a library that depends on dev versions — is not
		there.
	`tools/release/README.md`'s *"the bundler is not in the tree"* paragraph is
	corrected, and `dev/xhttp/VERSIONS.md` now exists (`#135` closed).
	**(c) F21 was tolerated, not settled.** `imports` takes a modpath spelled with
	dots from the loop and with slashes from one test, and normalises both.
- **The pybundle rewrite is at the spec-edit stage: the tests are re-derived, and
	the spec has not caught up with what they proved.** (Headline corrected
	2026-10-20: **the spec has caught up.** The decisions the tests asked for are
	written in as D20–D25 and the 2026-10-17 set D27–D34, and the tests have been
	re-derived against them — 203 in six files, all green, committed. **And on
	2026-10-21 the acceptance run added D38–D43 and nine more tests, 212 green.**
	What is below is the record of how it got there.) The human wrote `DRAFT.md`
	as intent; `SPEC.md` is derived from it and written by an AI on the condition
	that every decision traces back to a draft section (`24e1856`, `d9528b0`). The
	first test pass found **12 spec flaws** (`doc/reviews/pybundle-tests-pass1.md`,
	`608621e`) — places where a test could not be written without a decision the
	spec did not contain. All twelve are appended to `SPEC.md` as *Decisions — test
	pass 1* (`03c0e75`), written append-only: 346 insertions, 0 deletions, so
	nothing above the new section moved. The tests were then **re-derived on
	2026-10-15** against those decisions — 138 in five files, superseding the 65 —
	which is what pass 2's review (`doc/reviews/pybundle-tests-pass1-2.md`) records.
	**Two things follow from that; both are done now** (corrected 2026-10-20).
	First, five of the pass-1
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
- **The task store's schema defect is worse than `AQQNPAN` records, and it
	cost this session twice.** The ticket (2026-09-30) measured a 5-name header
	against an 8-column schema and a 62/14 split. **Measured 2026-10-21: the
	schema is 9 columns** (`description` was added), and the live file's 631
	data rows carry **three** widths — **70 at 5 fields, 209 at 8, 352 at 9** —
	under a header line that still names **5**. `taskupdate.py` itself is
	correct, because it reads **positionally** and guards with `len(row) >`; the
	trap is any **header-driven** reader, and `csv.DictReader` mis-maps
	`category` under `due_ts` and shifts everything after. **It happened twice
	in one session here**: a first parse of the store produced a wrong table,
	and a second, "corrected" parse was wrong in a different way — 177 open
	tasks against the store's true **89**, because the script compared
	`chg_ts` instead of taking the last row per id as the file's own rule says.
	**A quiet wrong answer is worse than a crash**, which is the ticket's own
	argument; the human's answer is that it is a symptom of the writer, and
	that **taskview should use `xcsv`** (see the `#96` entry above).
	Board: epiq `AQQNPAN` (Todo).
- **The notes file the secretary writes is not the one the secretary's id
	points at — `VYKTZRN` is live, not theoretical.** This session's canonical
	id is **`XLib/secretary-1`**, and `agent-coord.py note` accordingly returns
	`.agents/agent-notes-secretary-1.md`. **The previous session wrote to
	`agent-notes-secretary-3.md`** (last touched 09:37, against 09:20 for
	`secretary-1`), so the last session's context was in a file the id does not
	name, and finding it meant listing the directory and reading backwards. The
	notes files are also unbounded: `agent-notes-secretary-1.md` is **112 KB**
	and `agent-notes-secretary-3.md` 39 KB, against a rule that says instance
	notes are *"discarded on /new unless agent promotes"* — so they do not get
	discarded. The human's ruling on the protocol is at the ticket: at the
	start of every session, look through, promote what matters, then clear —
	**the tool can require it, it must not do it**. Board: epiq `VYKTZRN` (Todo).
- **taskview #96 is ruled and blocked, and the blocker was re-routed by the
	human on 2026-10-20.** The human settled four things on 2026-10-08: a
	separate `description` column on `tasks.csv`; exactly 2 tasks in full detail
	with the remaining pane space going to the condensed list; and the 2 always
	being the most urgent by due date (overdue first), regardless of day.
	**The human's answer to the header problem, 2026-10-20: it is a symptom.**
	`AQQNPAN` says the CSV header declares 5 columns while the rows carry 9, so
	a 9-column writer lands on a file whose header lies — and the human's answer
	is that **taskview should use `xcsv`, and `xcsv` needs to support reschema
	if it does not already. Once taskview uses xcsv, several solutions become
	simple and future schema changes become easier.** So `AQQNPAN` is no longer
	"fix the header": it is "make the schema change in a tool that can change
	schemas", which is a bigger and better-shaped piece of work. #96 is also
	still blocked on the human's ruling that every other open taskview ticket
	lands first. Board: epiq `XNTVCEE` (Todo). **And the `priority`-column
	question is answered by the same route** — the human's framing for the wide
	view is that **it always orders by due date**, so changing the order is
	simply a result of changing a due date, and a separate priority column is
	not wanted; the interaction is *editing* the due date (click a task, set
	`2026/10/27` directly, or bump it with `+7d`). That is `E5MH4S2`, the spec
	for the wide all-tasks view, and it is the next piece of this work.
	**RULED 2026-10-21, formally: the spec does NOT require a priority column.**
	The human: *"Make sure you remember, but don't otherwise work on that task."*
	That closes the question the ticket's own description calls *"the real
	content of this spec"*, and it closes the collision with the append-only
	last-write-wins model the description flagged. **Do not reopen it.** The
	ruling is on epiq `E5MH4S2` as a comment and in taskview `#151`'s own
	description; the task is **recorded, not worked on**.
- **`dev/xconf/`, `dev/xcsv/`, `dev/xschema/`, `dev/xtest/` use `tests/`.** The
	ruling is `test/`, recorded in `doc/development.md`; the rename is epiq
	`2VD2XZC`.
- **`tools/tool_schema_cache.py:14` still names this machine's absolute path in
	a tracked file, which `AGENTS.md` forbids, and nothing catches it.** The
	linter check exists — `check_absolute_paths`	(`tools/xlint/xlint.py:726`), and the ticket that asked for it
	(`7HP67R2`) is **closed** — but it runs in the **`.md` branch only**
	(`xlint.py:1008`). The `.py` branch has no absolute-path check, so the
	offending line, a path inside a module docstring, passes. **Re-measured
	2026-10-20: the file still carries `/storage/GitHub/Fun/XLib/tools/
	tool_schema_cache.py`, and `xlint .` over the whole repository is clean.**
	So the check landed for the case it was written for and the finding it came
	from is still open: either the check should cover `.py` as well, or the
	docstring should name the tool relative to the repository. The rule in
	`doc/paths-in-tracked-files.md` says "tracked files", which is every file,
	not only the Markdown ones.
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
	`tools/epiq-pending.py` reported **1 event still stranded** as of 2026-10-08
	(a bare `create.contributor` carrying no ticket content). **Re-measured
	2026-10-20: 0 stranded events.**
	`AZHG0FK` assumed the loss window was a worktree prune — a missing creation
	with committed events referencing it is more severe than that. Draining
	another actor needs a session running as that actor, which `epiq_actor_assume`
	refuses unless the server was launched with that name. The mechanism is
	per-actor and has no fix: each actor writes to
	`.epiq/events/<actorId>~pending*.jsonl`, which `.gitignore` deliberately never
	commits, and `epiq_sync` only ever drains the calling actor's own log.
- **One worktree hazard left, of the two reproduced 2026-10-08** (corrected
	2026-10-20). **`check-clean` answering `clean` for a dirty file in a worktree
	is FIXED and on master** — PR #47, `806253e` (`8FVW49J`): a worktree's `.git`
	is a *file*, so `nearest_git` walked past it to the parent repo and read the
	wrong status. The walk now stops at the checkout that owns the path, a
	worktree's `.git` counts whether it is a file or a directory, and a file
	behind a symlink is compared under the tracked name as well. **What is left
	here is the second half:** `.agents/` is gitignored, so a fresh worktree has
	no `claims.json` and claims resolve to the main checkout only — which is why
	the claims in this file's own state live in the root checkout while the code
	is worked on in `.work/`. **Corrected 2026-10-08**: an earlier line here said
	`check-clean` *refuses* worktree paths with "paths span multiple repos". It
	does not; that error needs two different repos in one call, and
	`.opencode/agent/` never triggers it because `abspath` does not follow the
	symlink.
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
	those 10 lines were counted as aligned code comments. **CLOSED, and the rule
	is written down** (epi `HRGFRWX`, closed): **`doc/style/python.md` now has a
	`## Docstrings` section**, and it says what was missing — module docstrings
	are prose, function docstrings follow the same principle, **no alignment
	columns in docstrings**, and docstrings are not exempt from the alignment
	rule (spaces are never used for alignment, in a docstring either). Same shape
	as `DDRBHD5`/`BX56XRY`/`13QYCT8`/`KJKEQ01`: a convention in wide use with no
	text behind it — and all four of those are closed too.
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
	indent**; that fragility is the stated reason. **Where the rule stands,
	re-measured 2026-10-20: it IS written into `doc/style/python.md` (`:108-109`
	— "spaces are never used for alignment anywhere in this repo") and is NOT
	into `AGENTS.md`'s `## Houserules`,** which the `0P2TVAM` precedent says it
	should be — so the "not yet written down" line was half stale. Measured
	scope when this was written: **369 lines in 47 tracked files** — 134 `.py`
	space-aligned comments, 135 Markdown alignment prose/tables, 100 other (epi
	`BSFQYPF`; reformat `F8XBH1F`). **The `.py` half has since been reworked**:
	`HRCQSV4` (the separate `def`/`class`-comment rule) and the mid-line
	double-space check are both closed and implemented, and **the repository is
	clean under them** (epi `13QYCT8`, `1YPFZYH`, both closed). **The Markdown
	half is not mechanized**, and the two questions the ruling does not answer
	are still the two that matter: **comment columns** (the biggest category,
	and the fragility argument applies to them as much as to signatures) and
	**Markdown tables**, where tabs do not render as padding so "use tabs" has no
	working answer. Board: epiq `BSFQYPF` (Todo) and `F8XBH1F` (Todo).
- **xlint's `check_def_one_line` was wrong in 74 of 74 cases — FIXED, and
	closed** (epi `1YPFZYH`, closed; the check was rewritten). The finding was
	right and the fix was to the *check*, not to the 74 lines: the old closing
	pattern was anchored `\s*$`, so every single-line `def` carrying a trailing
	comment was reported as a split signature. The check now distinguishes three
	states — closed on the line (clean whatever follows the colon, a trailing
	comment included), spanning lines in the permitted shape (clean), and a spill
	— and deciding the middle case needs `ast`, because whether the parameter
	list closes on its line is not a question a regex can answer without being
	fooled by a comment or a string. **Re-measured 2026-10-20: `xlint .` over
	the whole repository is clean, and `tools/taskview/test/` — where all 74
	once sat — is clean too.** The separate rule for a comment on a `def` or
	`class` line is the next bullet, and it landed as well.
- **xlint ran `check_trailing_whitespace` on `.py` and not on `.md` — FIXED, and
	closed** (epi `KJKEQ01`, closed). The `.md` branch now runs it, with the
	Markdown hard break — two trailing spaces, a documented CommonMark feature —
	exempted, which is the decision the finding asked for. **The finding's own
	correction is kept because it is the kind of thing that gets repeated: the
	rule was not *contradicted* by the absence of the check, it was merely
	absent, and "not implemented" is a different statement from "implemented
	backwards".** The 58 tracked `.md` lines that carried trailing whitespace are
	gone.
- **xlint had no mid-line double-space check — FIXED, and closed** (epi
	`13QYCT8`, closed). The finding was that the rule as stated would fight the
	repo's own house style: a prototype went 116 → 586 findings repo-wide, of
	which **134 were the `ClassName    # comment` column layout** used across
	`dev/xcsv`, `xlib/` and `dev/xschema`, and 120 more were SPEC.md alignment
	prose. **Exempting "data" was a ruling, not a detail**, and the ruling
	landed with the implementation: the check is `--no-double-space`-able, it
	takes an `is_py` argument, and the exemptions are by **replacement, never
	deletion** — deleting `` `<REF> ` `` from `...is \`<REF> \` — ref...`
	leaves two spaces and the line explodes (1879 vs 586 findings). **Re-measured
	2026-10-20: `xlint .` over the whole repository is clean under it.** The
	house style it was fighting with is the subject of the next bullet, and it
	is still open.
- **xlint had no check for a single trailing blank line — FIXED, and closed**
	(epi `BX56XRY`, closed). The finding was that the two file-ending checks did
	not compose into the rule either states: `check_final_newline` requires the
	file to end in a newline and `check_double_blank` rejects two consecutive
	blanks, so `import os\n\n` passed both — a real last line, one blank, and a
	present terminator. **The two blanks at the end *was* caught, which is the
	tell that `\n\n` was an oversight and not a policy.** `check_trailing_blank`
	now covers it, and it is the target the `.md` branch's double-blank check
	deferres to. **The four tracked files that hit it — the tool's own two entry
	points, `taskview.py` and `taskupdate.py`, among them — are fixed.** The
	deeper point in the finding stands as the reason it was worth a ticket: each
	check was written against its own symptom rather than against the rule, so
	neither composed.
- **xlint's merged-imports rule was unsatisfiable for aliased imports — FIXED,
	and closed** (epi `DDRBHD5`, closed). The human's ruling of 2026-10-09 was
	that **aliased imports get their own line, and should generally be avoided
	where avoidable — but xlint must handle them correctly**, and the code
	change was unambiguous: detect ` as ` explicitly, give aliased imports a
	branch, and do not propagate them as a mergeable predecessor. The finding
	recorded the trap precisely: `check_imports` decided plain-versus-dotted by
	testing the module text for a dot, and `import x as y` has no dot, so an
	aliased plain import was classified plain, flagged, **and propagated as a
	mergeable predecessor** — `import json` / `import math as m` /
	`import collections` produced two findings and **no rewrite that clears
	them**. The two aliased forms were treated oppositely for no reason but the
	dot: `import a.b as c` escaped the rule and `import math as m` did not.
	**Re-measured 2026-10-20: `xlint .` over the whole repository is clean.**
- **xlint does not lint tests — CORRECTED 2026-10-20: it does.** The exclusion
	this bullet describes is **gone**, and the ticket that carried it (`AK633QC`)
	is closed: `is_ignored` no longer excludes any path part named `test`, and
	`_BUILTIN_EXCLUDED` (`tools/xlint/xlint.py:34`) holds only `__pycache__`,
	`.git`, `node_modules` and `xlib_legacy`. **The claim had propagated here
	from an older reading and was never re-measured** — the same failure the
	html work found elsewhere, where a fixed record was quoted as a live one.
	The 109 / 103 / 5 / 1 breakdown went with it. **What is left of the original
	finding is the other half**, and it still stands: **`tests/` — the name the
	house rules call wrong — is not excluded either**, so `2VD2XZC`'s rename
	moves four libraries *into* coverage rather than out of it, and the question
	the ticket asked — narrow the exclusion to foreign test data, or write down
	that tests are exempt — is moot in the other direction. `XCKN0AT`'s
	pre-commit hook inherits whatever `is_ignored` does, so it inherits the fix
	too.
- **Task scheduling** (re-measured 2026-10-20): the counts this line carried
	are stale in both directions. **The 4 high-importance tasks with no due date
	have all been given one** — #52 → 2026-10-30, #61 → 2026-10-21, #63 →
	2026-11-06, #75 → 2026-10-23. **17 open tasks are past due**, not 10, and
	that number moves hourly. **16 open tasks have no due date at all**, and they
	are a different set: #104–#110, #122, #123, #127, #133, #137, #138, #140,
	#141, #143. The store is the record; `TASKS.md` holds this workspace's
	**28** open items, not two.
- **The repository's guard over its own test layout is red — eight modelbench
	test files are unreachable by the one command meant to run them.** Measured
	2026-10-21: `python3 tools/run_tests.py` gives **12 suites passed, 2 failed**,
	and the two are `tools/test` and `dev/xhttp/test`. The `dev/xhttp` half is
	the known `ContentNegotiationTest` six (`BFNRBG7`). **The `tools/test` half
	is new**, and it is the guard that exists for exactly this failure:
	`tools/test/test_suites.py:test_every_test_file_is_in_a_suite_or_a_listed_exception`
	fails with **"test files that no runner reaches"** — all eight in
	`tools/modelbench/test/` (`test_bench_mapping_hash.py`,
	`test_compliance_protocols.py`, `test_db_regrade.py`,
	`test_harness_mapping.py`, `test_ledger_state.py`,
	`test_provider_error.py`, `test_raw_data.py`, `test_review_vocabulary.py`).
	`run_tests.py`'s `SUITES` list has no `tools/modelbench/test` entry. **The
	eight files pass on their own — 77 tests, 0 failed** — so the fix is the one
	line the guard is asking for. **The cause is the modelbench work of
	2026-10-20/21** (PRs #62–#67, #70), which added test files without adding
	the suite. This is the failure class the guard was written for: *"a suite
	that cannot be run is a suite that does not exist"*, and this one reported
	success over content it never examined. **Filed as epiq `QPDJ8RF`,
	taskview `#179`.**
- **`RX5H4P3` reproduces, and it is a spec-conformance defect rather than a
	design fork.** The bundler renames a module global to its prefixed name, and
	a function parameter carrying the same name is a name defined inside the
	function — so **R4 says it must not be translated**
	(`tools/pybundle/SPEC.md:100-104`: *"A name defined inside a function or
	class blocks translation of that name within it, so shadowing does not
	break"*). **Measured 2026-10-21**: a module with `VALUE = 42` and
	`def compute(VALUE): return VALUE + 1` bundles to
	`def mod__helper__compute(mod__helper__VALUE): return VALUE + 1` — the
	parameter is renamed on the def line and **the body's use of it is not**.
	The bundle **compiles clean** and then raises **`NameError: name 'VALUE' is
	not defined`** the first time the function is called. **The spec already
	rules it**, so it needed no decision from the human — only an implementer.
	**Fixed the same day**, as part of the acceptance repair: a parameter is a
	name the function binds, so it is not translated (spec D40), and the bundle
	runs where it used to raise. Taskview `#178` done, epiq `RX5H4P3` in Done,
	commit `a9b9fe5` on `fix/JD9DWVN-bundle-traveller` (PR #76).
- **`2VD2XZC`'s blocker was already resolved in this file on 2026-10-20, and the
	board ticket still carries the old answer.** The xlint bullet above records
	that `is_ignored` no longer excludes any path part named `test`, so the
	rename moves four libraries **into** coverage rather than out of it, and the
	fork the ticket recorded — widen the exclusion set, or accept the loss — is
	moot. **The ticket has not been re-read since**: its last comment
	(2026-10-01) still says *"ai-ok removed"* and *"the fork … is still
	unmade"*. **Re-measured 2026-10-21**: `python3 tools/xlint/xlint.py
	dev/xcsv/tests/test_xcsv.py` → `clean`, the same over a `test/` folder
	(`dev/xhttp/test/test_response.py`) → `clean`, and `.xlintignore` excludes no
	test folder. So the rename is a **pure rename**: four `git mv`s, four lines
	in `tools/run_tests.py`, and the human's ruling of 2026-09-30
	(`doc/development.md:140-142`) becomes true rather than outstanding. **A
	scope question the ticket does not settle**: `xlib_dev/tests/` is a fifth
	folder with the old name, and `xlib_dev/` is not a dev folder — the ruling
	says "a library's tests go in a `test/` folder in its dev folder". **The
	`ai-ok` tag was deliberately not restored** — "In progress" means the human
	has ai-ok'd the ticket, and the tag came off because this fork was unmade,
	which was right at the time. The fork is moot now, so the ticket is ready
	for the human's `ai-ok` and that call is theirs. **Now taskview `#180`
	(due 2026-10-27); the re-measurement is on the ticket as a comment.**
- **Every dev library now says who wrote it, in the same section of a README.**
	Ruled by the human, 2026-10-21: `dev/xhttp` and `dev/xprod` are
	**hand-written**, and the other four are **AI-written** — so the four say
	**the opposite**. **Four READMEs are new** (`xconf`, `xcsv`, `xschema`,
	`xtest` had a SPEC.md and no README), and each carries an **"XLib rules"**
	section in the same shape as the two hand-written ones. **The convention now
	exists, but only in the six READMEs** — no rule file carries it, so nothing
	announces it and nothing enforces it; `doc/development.md:94` still covers
	only the AI-written *spec* marker. **The two hand-written READMEs are still
	uncommitted and are not mine**, and they **disagree on heading level** —
	`dev/xhttp/README.md` uses `##` and `dev/xprod/README.md` uses `#`. And
	`dev/xprod` still has no SPEC.md or VERSIONS.md at all (`DCF9EHW`).
- **Herdr now reports every open window's live session, and the running windows
	picked the integration up without a restart.** The integration was installed
	on 2026-10-21 and **verified in a fresh window** first — a pane launched
	through `tools/oc-agent` reported `agent_session.source = "herdr:opencode"`,
	the session id herdr named was the one marduk's registry named, and
	`screen_detection_skipped` was true. **Then the four windows that were
	already open were re-read, and they report too**: every pane has
	`screen_detection_skipped = true` and a session id, and **every one of those
	ids is the same session the `instance-report` plugin reports for the same
	process** — `wK:p1` `secretary-3` `ses_ea2b1cd8…`, `wK:p2` `secretary-4`
	`ses_ea2c1eda…`, `wJ:p1` `secretary` `ses_ea2c55ab…`, `wM:p1` `secretary-2`
	`ses_ea611963…`. **Two independent mechanisms, one answer** — which is the
	kind of agreement worth having, and it is the fact `NAHEGJE` was filed for.
	**The premise that a running TUI does not pick up a newly installed plugin
	was an inference, and the measurement refuted it.** Taskview `#181` (done).
- **The window's name has two owners, and the one that is under version control
	is the one that does the naming.** Measured on all four windows: the service
	reports the session titles as `secretary`, `secretary-2`, `secretary-3`,
	`secretary-4` — the launcher's names, written by `tools/oc-agent:80-81` (the
	OSC title) and `tools/oc-agent:128-132` (the session title). **The
	`agent-title` plugin never fires in an `oc-agent` window**: its guard
	(`agent-title.ts:96-113`) renames only a default title or its own previous
	name, and "secretary-3" is neither. **The fork is the human's** — the
	launcher keeps the name and the plugin stops trying, or the plugin takes the
	name and must learn the slot from the registry. Filed as epiq `TWA3Z0X`
	(Todo), taskview `#182` (by decision needed); the plugin's file is outside
	every repository, which is the Agents board's `M9J6F8W`.

## Settled — not to be reopened without cause

- **`git checkout` is banned outright, in every repo, as of 2026-10-19.** Use
	`git switch` to change branch and `git restore` to change a file. The human's
	reasoning: it does not mean changing branch is always right — *"often when an
	agent wants to switch branches I actually want it to use a worktree instead"* —
	but `git switch` *"is at least not going accidentally delete changes"*, and
	`git checkout` *"essentially functions as git reset"*. **Blanket ban until
	further notice**, on the strength of several accidental deletions rather than
	one. Written in both rule sets: `doc/working-tree.md` here (and widened in
	the `AGENTS.md` pointer row so it shows in the index) and a
	`` `git checkout` is banned `` section in the Agents workspace's `AGENTS.md`. **The safety property
	is structural, not conventional**, and was measured rather than asserted:
	`git switch -- f.txt` fails with `fatal: invalid reference: f.txt` (exit 128),
	so the destructive form cannot be typed — while `git checkout -- f.txt` took an
	uncommitted edit from `UNCOMMITTED WORK` to `committed` with no warning and
	nothing to undo. **Worktree first, always**: `git worktree add` leaves the
	human's and other agents' uncommitted work where it is, and opencode can move
	a session into a worktree it just created. **Enforcement is not built**
	(`#141`): the live guard would be a global opencode plugin on
	`tool.execute.before`, and the durable one an xlint rule on the literal string.
	→ `doc/working-tree.md`, taskview `#141`
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
3. **The stranded-event mechanism has no fix, but nothing is stranded now.**
	The mechanism is understood — per-actor logs, and `epiq_actor_assume` refuses a
	name its server was not launched with — so this is no longer a mystery but a
	decision: one session per stranded actor, which means the human launching it,
	or a change to epiq itself. **Re-measured 2026-10-20:
	`tools/epiq-pending.py` reports 0 stranded events**, where it reported 1
	(a bare `create.contributor` carrying no ticket content) on 2026-10-08. It
	stays open because the *mechanism* has no fix, and the next agent to exit
	without syncing restarts the count.
4. **Should `release.py` tag or commit a release?** It currently does neither,
	there are zero tags in the repo, and the README's scope section may mean that
	is deliberate. If deliberate it should be written down; if not it belongs in
	`1ZY2Q5Q`. Related: `Z491RDN`'s "entry written when the change reaches master"
	has no tooling behind it.
5. ~~**Three pull requests rewrote `STATUS.md` from the same base, and merging
	them meant three hand-resolutions.** They conflicted because each was written
	as a snapshot of the moment before its own merge, so the merged file had to
	pick one version of every shared claim. That happened twice already (#1/#11,
	then this run) and will happen again while state-file rewrites are a
	per-ticket deliverable. Worth deciding whether a STATUS.md rewrite is a
	ticket of its own or a final step of the merge, since the second stops two
	agents racing for it.~~ **ANSWERED 2026-10-21: it is a final step of the
	merge, and it is no longer a per-ticket deliverable at all.** The human
	ruled that the per-person state files are written by the secretary **at merge
	time** (epiq `5S8FY10`, PR #79) — so a branch does not carry them, which is
	what stops two agents racing for them. **The question was open in this file
	while the ruling was being prepared.**
6. **Should `doc/style/prose.md` bind dispatched workers too?** The rule file
	is reachable through `AGENTS.md`, which every agent reads, but a subagent
	runs from its own prompt in `.opencode/agent/` and does not necessarily get
	`AGENTS.md` in context. If the prose rules are meant to apply to worker
	output too, that needs a mechanism; today they bind the agents that read the
	repo rules. `KDX7KWJ` closed without deciding it.
7. **`xlib_dev` shipped to master** (taskview #112 done, epiq `ASTXNPG` Done,
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
	uncommitted. **(Corrected 2026-10-20: master was one commit ahead of origin
	and unpushed at the time; it is now in step with `origin/master` at
	`fb82f12`.)**
8. **Correction: there is no broken namespace-package import in `dev/`.** I told
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
9. **A dotted non-local import leaks one unprefixed name — RULED 2026-10-17:
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
