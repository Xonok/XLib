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
