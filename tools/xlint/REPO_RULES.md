# xlint — repo-specific rules

A checkout can carry its own lint policy without editing the shared
`tools/xlint/xlint.py`. The policy is arbitrary Python, so a rule can check
anything: a token in a file, an import graph, a set of files compared with one
another.

## Where it lives

- **Default:** `<checkout>/tools/xlint_rules.py`. If the file exists, xlint
	loads it; no configuration is needed.
- **Backup:** `.xlint.toml` with `[rules] path = "..."`, relative to the
	checkout root. It is only needed when the default location does not fit — a
	test file, a split rules package. A config without `[rules]` means the
	default. Neither file means no repo rules, and xlint behaves as it did
	before.
## Disabling rules

A checkout can disable rules locally in `.xlint.toml`, without editing the
module or passing flags on every invocation. Disabled rules are skipped for
that checkout only.

```toml
# Disable by name — built-in ids and repo rule names both work.
disable = ["space-indent", "flag"]

# Or, equivalently:
[disable]
space-indent = true
flag = true
```

Built-in rules are identified by their `--no-*` flag name without the `no-`
prefix (`double-blank`, `space-indent`, `trailing`, `js-trailing`, ...).
Repo rules are identified by the `name` their module gives them. The special
names `*` and `repo-rules` disable every repo rule in the checkout.

A `[rules]` table may also carry the list when no module path is needed:

```toml
[rules]
disable = ["flag"]
```

An empty or absent disable list leaves every rule in force. A malformed entry
(a non-string, an empty name, or a non-boolean value) is a hard error naming
the config file.

- **One per checkout.** A worktree is its own checkout and carries its own
	tracked copy. A nested checkout's module governs its files. A path outside
	any checkout has no repo rules.
- The configured path must stay inside the checkout: an absolute path, or one
	that climbs out with `..`, is an error. It does not silently load a file the
	repository does not carry.

## The contract

```python
def rules():
	return [
		{"name": "no-xlib-dev", "paths": ["xlib/**"], "check": check_no_xlib_dev},
	]

def check_no_xlib_dev(files):
	# files: [(Path, list[str])] selected by paths; called once, so cross-file logic works.
	return [(path, line, "a released file must not mention xlib_dev")]
```

- `rules()` returns a list. Required: `name` (unique within the module) and
	`check` (callable). Optional: `paths` — globs in the `.xlintignore` pattern
	language, relative to the checkout root. Omitting `paths` selects every file
	xlint visits.
- `check(files)` receives `(Path, decoded lines)` for every selected file, and
	returns `(path, line, message)`. `line` is 1-based; `None` is a file-level
	finding. The rule may read other files, import modules, use the AST, or run
	a subprocess — any Python condition.
- There is no `contains`, `exclude` or `tracked_only`: a rule filters its own
	paths, and an unrecognised key is an error rather than a silent no-op.

## Failure

An import error, a missing `rules()`, a malformed mapping, a duplicate name or
an exception from a rule is a hard error naming the module and rule. The run
exits 1 and never reports a pass: a rule that did not run must not look like a
rule that found nothing. `--no-repo-rules` skips loading them.

## Watch mode

The default module, `.xlint.toml`, and the file the config points to are watch
targets. Editing one reloads the module and redraws the report. A module that
fails to load is shown in the report and retried when the module or config
changes, rather than ending the watch.

## Trust

The module is repository code executed in-process on every run, including the
pre-commit hook. That is the cost of arbitrary logic; it is wider than the
built-ins, but the same category as the branch's own `xlint.py` being what
runs. A rule that hangs hangs the run.
