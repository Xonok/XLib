# Library structure

Reference, not rules. AGENTS.md carries what an agent must follow on every edit;
this file carries how a library is actually shaped, so that AGENTS.md stays a
rules file. Read this when working *on* library code — layout, release naming,
import resolution, and what the bundler does to names.

No absolute machine paths here: a tracked file syncs between machines. Machine-
specific locations belong in the Agents workspace's `.agents/machine-info.md`.

## Repo layout

| Path | What lives there |
|------|------------------|
| `dev/<library>/` | one folder per library under development |
| `xlib/` | released, versioned, self-contained single files |
| `tools/<tool>/` | tools and scripts, developed like libraries but never released |
| `doc/` | process, style rules, plans, reviews, audits |
| `personal/<person>/` | `STATUS.md`, `TASKS.md`, `HISTORY.md` |
| `xlib_legacy/` | prior art, reference only — nothing imports it |

## A library's dev folder

```
dev/xcsv/
	xcsv.py          entry point: the public interface, and nothing else
	_/               internal modules, prefix-avoided by the bundler
		__init__.py
		csv_tok.py
		csv_ser.py
	tests/           tests (the ruling is `test/`; four libraries are being renamed)
	SPEC.md          the map: modules, data flow, invariants, decisions
	VERSIONS.md      one entry per release, newest first
```

- **One entry point**, named after the folder: `dev/xcsv/` → `xcsv.py`.
- **Internal helpers live in other files**, so the entry file stays the public
	interface. `<library>_tok.py` and friends.
- **`_/` holds internals** when a library has enough of them. It may have an
	`__init__.py`; the library root may not.
- **The root must not contain `__init__.py`.** Dev folders are not packages —
	they are imported as `from xcsv.xcsv import ...`, which works by path, not by
	being a package.
- `SPEC.md` and `VERSIONS.md` are per library. Tools and scripts that aren't
	versioned don't need a `VERSIONS.md`; they may still want a SPEC (marduk,
	pybundle and taskview have one).

## Release naming

Released files are `xlib/<library>_<major>_<minor>_<revision>.py`, e.g.
`xlib/xcsv_1_1_0.py`. The scheme is `libraryname_major_minor_revision.py` — note
the separator is an underscore, and the library name may itself contain one
(`net5_27_105.py`).

Choosing the bump:

| Bump | For | Gate |
|------|-----|------|
| **revision** | bugfixes only; no features, no API change | none — this is the default |
| **minor** | additions that don't break previous users | "breaking" = a user would have to adapt |
| **major** | dropping deprecated code | breaking changes **and** time since the last major |

Cosmetic issues are not bugs and are fixed without a bump. A first release is
always `1_0_0`; after that the script reads the latest version in `xlib/`.
Deprecations are marked in version terms and dropped after exactly 2 major
versions.

The mechanics live in `tools/release/README.md` — including that
`release.py <library>` always writes, with no dry run.

## Imports

Three forms, and which one is allowed where:

```python
from xlib import xcsv_1_1_0          # explicit version — what libraries use
from xlib import xcsv                # unversioned — for users of the library
from xcsv.xcsv import read_line      # a dev folder importing itself
```

- **Libraries never use versionless imports**, not even in development: always
	an explicit released version, `from xlib import libraryname_5_9_27 as ...`.
	Each library pins the exact public version of each requirement, and cannot be
	released until all of them are.
- **Tests are the exception.** A test in a dev folder imports the library under
	development unversioned (`from xlib import xtest` or `from xtest import
	xtest`), because testing the code being developed is the point.
- **A user of a released library** can import either way; that is why both work.

`xlib/__init__.py` resolves an unversioned name to a file. It looks for a
top-level `xlib_pins` module and, if the name is pinned there, uses that
version; otherwise it takes the highest version on disk. There is no
`xlib_pins` module in the repo, so resolution is currently latest-on-disk.

## The bundler and the public API

`tools/release/release.py` packs a dev folder into one file via the bundler
(`tools/pybundle/bundler.py`). Two consequences shape how a library is written:

**1. Internal names get prefixed.** Every module's top-level names are mangled
with a flat prefix — dots become underscores — so `tokenize` in `csv_tok.py`
becomes `csv_tok_tokenize` and cannot collide with another module's `tokenize`.
Imports of those names are rewritten to match.

**2. Therefore the public API must be *defined* in the entry file**, not
imported from an internal module and re-exported. A re-exported name would be
prefixed at bundle time and stop being the name the caller used. Use a thin
wrapper:

```python
from ._.csv_tok import tokenize as _tokenize

def tokenize(line):
	"""Split a CSV line (with // comments and quoting) into cells."""
	return _tokenize(line)
```

Relative imports between a library's own modules are the bundler's problem, not
yours: it resolves and inlines them.

The bundler does **not** resolve cross-library imports. A dependency line like
`from xlib import somelib_5_9_27` is emitted as written — which is exactly why
libraries pin explicit versions.

The current bundler's design is described in `tools/pybundle/SPEC.md`. A rewrite
is in progress against a new spec (epi `6MFX0Z1`); `doc/plans/bundler.md` holds
the abandoned redesign attempt, and the reviews in `doc/reviews/` that look like
they review the current bundler do not — read `doc/reviews/README.md` first.
