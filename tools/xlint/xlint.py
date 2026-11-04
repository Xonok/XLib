#!/usr/bin/env python3
"""xlint — the repository's style checker.

Package entry point. The implementation lives in the sibling modules; this file
is the orchestrator: it makes the package importable both as a module and when
run directly, pulls in the siblings' public names, and dispatches to the CLI.
Nothing here runs at import time beyond defining names, so import order does
not affect behaviour.
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

# Dependencies. Relative imports only: this module is always loaded as part of
# the tools.xlint package (either imported or via the __package__ assignment
# above), so the absolute-import fallbacks are not needed.
from ._io import _libc,_inotify_failure,_Exclusions,_compile_pattern,_glob_to_regex,_is_checkout_root,find_exclusion_chain,find_exclusion_roots,find_checkout_root,exclusion_reason,is_ignored,excluded_paths,lint_files,stamp,_IgnoreRules,_is_tracked_file,_here,_DEF_PREFIX_RE,_SPACE_INDENT_RE,_ALIASED_NAME_RE,_CLEAR_SCREEN,_ENTER_WATCH,_LEAVE_WATCH,NAME,_EVENT_HEADER,_IN_CLOSE_WRITE,_IN_MOVED_FROM,_IN_MOVED_TO,_IN_CREATE,_IN_DELETE,_IN_DELETE_SELF,_IN_MOVE_SELF,_IN_IGNORED,_IN_ISDIR,_WATCH_MASK,_BUILTIN_EXCLUDED,_IGNORE_FILE,_POLL_SECONDS,_INOTIFY_ADVICE,_JS_SUFFIXES,_PY_MD_SUFFIXES,_HTML_SUFFIXES,_C_SUFFIXES,_SH_SUFFIXES,_ALL_SUFFIXES,_RULE_MODULE_SERIAL,_BUILTIN_DISABLES,_DOUBLE_SPACE_RE,_ABSOLUTE_PATH_RE
from . import _io
from ._repo_rules import _RepoRuleError,_select_all,_selection,_validate_rules,_findings,_load_rules,_canonical_disable,_add_disabled,_parse_disabled,_RepoModule,_RepoRules,_Rules,_disabled_canonical,_apply_disabled_to_args
from ._checks import check_double_blank,check_space_indent,check_space_indent_exempt,check_trailing_whitespace,check_double_space,_line_has_double_space,check_absolute_paths,check_trailing_blank,check_final_newline,check_leading_blank,check_file,_Check,_LANGUAGE_CHECKS,_SUFFIX_TO_LANGUAGE
from ._markdown import _frontmatter_exempt,_fence_exempt,_markdown_exempt_spans,_blockquote_exempt
from ._python import _python_exempt_spans,_python_string_lines,_python_docstring_lines,_is_permitted_multiline,_one_argument_per_line,_spanned_def_lines,_signature_end,_is_gap,check_def_one_line,_def_lines,_comment_lines,check_def_comment,check_imports
from ._js import check_js_trailing_whitespace,check_js_double_blank,check_js_space_indent,check_js_final_newline,check_js_trailing_blank,_js_exempt_spans,_js_exempt_lines
from . import _html
from . import _personal
from . import _banned_git
from . import _c
from ._watch import _InotifyWatcher,_PollWatcher,make_watcher,_watch_cursor,_finding_text,_finding_key,_write_output,draw,_repo_report,watch
from . import _watch
from ._cli import main

if __name__ == "__main__":
	sys.exit(main())
