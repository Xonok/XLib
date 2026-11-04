#!/usr/bin/env python3
"""xlint — the repository's style checker.

Package entry point and public API. The implementation lives in the
sibling modules; this file is the orchestrator: it makes the package
importable both as a module and when run directly, imports each sibling
once, and rebinds every name they expose so the whole public API is
visible and explicit here. Nothing runs at import time beyond defining
names, so import order does not affect behaviour.
"""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
	sys.path.insert(0, str(_here))

if __package__ is None:
	_repo_root = str(Path(__file__).resolve().parents[2])
	if _repo_root not in sys.path:
		sys.path.insert(0, _repo_root)
	__package__ = "tools.xlint"

# Sibling modules, imported once.
from . import _io
from . import _repo_rules
from . import _checks
from . import _markdown
from . import _python
from . import _js
from . import _html
from . import _personal
from . import _banned_git
from . import _c
from . import _watch
from . import _cli

# Public API: explicit rebinding of every name each sibling exposes.
_libc = _io._libc
_inotify_failure = _io._inotify_failure
_Exclusions = _io._Exclusions
_compile_pattern = _io._compile_pattern
_glob_to_regex = _io._glob_to_regex
_is_checkout_root = _io._is_checkout_root
find_exclusion_chain = _io.find_exclusion_chain
find_exclusion_roots = _io.find_exclusion_roots
find_checkout_root = _io.find_checkout_root
exclusion_reason = _io.exclusion_reason
is_ignored = _io.is_ignored
excluded_paths = _io.excluded_paths
lint_files = _io.lint_files
stamp = _io.stamp
_IgnoreRules = _io._IgnoreRules
_is_tracked_file = _io._is_tracked_file
_here = _io._here
_DEF_PREFIX_RE = _io._DEF_PREFIX_RE
_SPACE_INDENT_RE = _io._SPACE_INDENT_RE
_ALIASED_NAME_RE = _io._ALIASED_NAME_RE
_CLEAR_SCREEN = _io._CLEAR_SCREEN
_ENTER_WATCH = _io._ENTER_WATCH
_LEAVE_WATCH = _io._LEAVE_WATCH
NAME = _io.NAME
_EVENT_HEADER = _io._EVENT_HEADER
_IN_CLOSE_WRITE = _io._IN_CLOSE_WRITE
_IN_MOVED_FROM = _io._IN_MOVED_FROM
_IN_MOVED_TO = _io._IN_MOVED_TO
_IN_CREATE = _io._IN_CREATE
_IN_DELETE = _io._IN_DELETE
_IN_DELETE_SELF = _io._IN_DELETE_SELF
_IN_MOVE_SELF = _io._IN_MOVE_SELF
_IN_IGNORED = _io._IN_IGNORED
_IN_ISDIR = _io._IN_ISDIR
_WATCH_MASK = _io._WATCH_MASK
_BUILTIN_EXCLUDED = _io._BUILTIN_EXCLUDED
_IGNORE_FILE = _io._IGNORE_FILE
_POLL_SECONDS = _io._POLL_SECONDS
_INOTIFY_ADVICE = _io._INOTIFY_ADVICE
_JS_SUFFIXES = _io._JS_SUFFIXES
_PY_MD_SUFFIXES = _io._PY_MD_SUFFIXES
_HTML_SUFFIXES = _io._HTML_SUFFIXES
_C_SUFFIXES = _io._C_SUFFIXES
_SH_SUFFIXES = _io._SH_SUFFIXES
_ALL_SUFFIXES = _io._ALL_SUFFIXES
_RULE_MODULE_SERIAL = _io._RULE_MODULE_SERIAL
_BUILTIN_DISABLES = _io._BUILTIN_DISABLES
_DOUBLE_SPACE_RE = _io._DOUBLE_SPACE_RE
_ABSOLUTE_PATH_RE = _io._ABSOLUTE_PATH_RE
_RepoRuleError = _repo_rules._RepoRuleError
_select_all = _repo_rules._select_all
_selection = _repo_rules._selection
_validate_rules = _repo_rules._validate_rules
_findings = _repo_rules._findings
_load_rules = _repo_rules._load_rules
_canonical_disable = _repo_rules._canonical_disable
_add_disabled = _repo_rules._add_disabled
_parse_disabled = _repo_rules._parse_disabled
_RepoModule = _repo_rules._RepoModule
_RepoRules = _repo_rules._RepoRules
_Rules = _repo_rules._Rules
_disabled_canonical = _repo_rules._disabled_canonical
_apply_disabled_to_args = _repo_rules._apply_disabled_to_args
check_double_blank = _checks.check_double_blank
check_space_indent = _checks.check_space_indent
check_space_indent_exempt = _checks.check_space_indent_exempt
check_trailing_whitespace = _checks.check_trailing_whitespace
check_double_space = _checks.check_double_space
_line_has_double_space = _checks._line_has_double_space
check_absolute_paths = _checks.check_absolute_paths
check_trailing_blank = _checks.check_trailing_blank
check_final_newline = _checks.check_final_newline
check_leading_blank = _checks.check_leading_blank
check_file = _checks.check_file
_Check = _checks._Check
_LANGUAGE_CHECKS = _checks._LANGUAGE_CHECKS
_SUFFIX_TO_LANGUAGE = _checks._SUFFIX_TO_LANGUAGE
_frontmatter_exempt = _markdown._frontmatter_exempt
_fence_exempt = _markdown._fence_exempt
_markdown_exempt_spans = _markdown._markdown_exempt_spans
_blockquote_exempt = _markdown._blockquote_exempt
_python_exempt_spans = _python._python_exempt_spans
_python_string_lines = _python._python_string_lines
_python_docstring_lines = _python._python_docstring_lines
_is_permitted_multiline = _python._is_permitted_multiline
_one_argument_per_line = _python._one_argument_per_line
_spanned_def_lines = _python._spanned_def_lines
_signature_end = _python._signature_end
_is_gap = _python._is_gap
check_def_one_line = _python.check_def_one_line
_def_lines = _python._def_lines
_comment_lines = _python._comment_lines
check_def_comment = _python.check_def_comment
check_imports = _python.check_imports
check_js_trailing_whitespace = _js.check_js_trailing_whitespace
check_js_double_blank = _js.check_js_double_blank
check_js_space_indent = _js.check_js_space_indent
check_js_final_newline = _js.check_js_final_newline
check_js_trailing_blank = _js.check_js_trailing_blank
_js_exempt_spans = _js._js_exempt_spans
_js_exempt_lines = _js._js_exempt_lines
_InotifyWatcher = _watch._InotifyWatcher
_PollWatcher = _watch._PollWatcher
make_watcher = _watch.make_watcher
_watch_cursor = _watch._watch_cursor
_finding_text = _watch._finding_text
_finding_key = _watch._finding_key
_write_output = _watch._write_output
draw = _watch.draw
_repo_report = _watch._repo_report
watch = _watch.watch
main = _cli.main

if __name__ == "__main__":
	sys.exit(main())
