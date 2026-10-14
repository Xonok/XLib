# Reviews

Review documents, named `<library>-<hash>.md`, where `<hash>` is a content hash
of the dev folder at review time — so a changed folder makes a review stale by
its name.

## The pybundle reviews describe files that are not in the tree

Four of the documents here review a **single-pass pybundle redesign that was
never committed**:

- `pybundle-review.md`
- `pybundle-review-2026-09-10.md`
- `pybundle-review-next.md`
- `pybundle-23efebb3.md`

They review `pybundle/pybundle.py`, `pybundle/BUG_FIX_SPEC.md` and
`pybundle/VERSIONS.md` (1_0_0–1_0_3), and three fixtures — `self_alias`,
`pep420_implicit`, `entry_only_imports` — that were never added. None of those
files exist. The attempt was real, it stalled on the complexity of the existing
bundler, and the reviews record a genuine round of work; they are **not a
verdict on the code that is in the tree**.

The bundler that existed when these were written — the five-phase implementation
in `tools/pybundle/bundler.py` + `bundler_impl.py`, with 7 fixtures — **was
deleted on 2026-10-14** (`5e87ae8`), ahead of the rewrite. So the warning above
now applies twice over: these reviews describe files that were never committed,
and the code they were written against no longer exists either.
`tools/pybundle/` holds documents and no code — `DRAFT.md` (the human's intent),
`SPEC.md` (derived from it, and the spec the rewrite follows), `SPEC_old.md`
(this old spec, renamed, describing the deleted bundler) and `SPEC_new.md` (an
earlier handwritten attempt). See epiq `6MFX0Z1`; the discussion the reviews
belong to is in `doc/plans/bundler.md`.

Kept deliberately, on the human's ruling (2026-09-30): note the facts, leave the
files in place. Do not cite these reviews as evidence about the current bundler,
and do not treat a fixture or file they mention as something to implement.

## The rest

- `xcsv-81f355dd.md` — the review behind the `1_1_0` release.
- `taskview-2026-09-08*.md` (3 versions) and `taskview-2026-09-27-a9ee0a.md` —
	the filter feature, newest last. Named by date rather than by content hash,
	which breaks the staleness detection above. The filter it reviews is built;
	its plan (`doc/plans/taskview-filter.md`) was deleted 2026-09-30.
