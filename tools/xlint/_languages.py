"""Language-to-rules mapping for xlint.

This module does nothing else: it maps file suffixes to a language code, maps each
language code to the list of checks that apply, and defines the `_Check` descriptor
that a check list is made of. The check implementations live in `_checks.py` and
the surrounding modules; they are imported lazily here so this module can be
loaded without pulling them in at import time.
"""

# --- Suffixes ---------------------------------------------------------------

_JS_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx")

_PY_MD_SUFFIXES = (".py", ".md")

_HTML_SUFFIXES = (".html",)

_C_SUFFIXES = (".c", ".h")

_SH_SUFFIXES = (".sh",)

_ALL_SUFFIXES = _PY_MD_SUFFIXES + _JS_SUFFIXES + _HTML_SUFFIXES + _C_SUFFIXES + _SH_SUFFIXES

# --- Suffix -> language -----------------------------------------------------

_SUFFIX_TO_LANGUAGE = {}
for _s in (".py",):
	_SUFFIX_TO_LANGUAGE[_s] = "py"
for _s in (".md",):
	_SUFFIX_TO_LANGUAGE[_s] = "md"
for _s in _JS_SUFFIXES:
	_SUFFIX_TO_LANGUAGE[_s] = "js"
for _s in _HTML_SUFFIXES:
	_SUFFIX_TO_LANGUAGE[_s] = "html"
for _s in _C_SUFFIXES:
	_SUFFIX_TO_LANGUAGE[_s] = "c"

# --- Descriptor -------------------------------------------------------------

class _Check:
	"""One entry in a language's check list.

	`attr`/`name` are the disable flag attribute and canonical rule name;
	`rule` is the rule id reported; `produce` returns (line, message) pairs.
	"""

	__slots__ = ("attr", "name", "rule", "tracked_only", "produce")

	def __init__(self, attr, name, rule, produce, tracked_only=False):
		self.attr = attr
		self.name = name
		self.rule = rule
		self.tracked_only = tracked_only
		self.produce = produce

# --- Per-language check lists -----------------------------------------------
# Each function imports its dependencies lazily so this module stays free of
# import-time side effects and circular imports.

def _py_checks():
	from ._checks import (check_leading_blank,check_double_blank,check_space_indent_exempt,
		check_trailing_whitespace, check_def_one_line, check_def_comment, check_trailing_blank,
		check_final_newline, check_imports, check_double_space, check_absolute_paths)
	from ._python import _python_string_lines,_python_docstring_lines

	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_double_blank", "double-blank", "double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_space_indent", "space-indent", "space-indent", lambda lines, text, path, tracked: check_space_indent_exempt(text, _python_string_lines(text))),
		_Check("no_trailing", "trailing", "trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text)),
		_Check("no_def_one_line", "def-one-line", "def-one-line", lambda lines, text, path, tracked: check_def_one_line(text)),
		_Check("no_def_comment", "def-comment", "def-comment", lambda lines, text, path, tracked: check_def_comment(text)),
		_Check("no_final_newline", "final-newline", "final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
		_Check("no_imports", "imports", "imports", lambda lines, text, path, tracked: check_imports(text)),
		_Check("no_double_space", "double-space", "double-space", lambda lines, text, path, tracked: check_double_space(text, True)),
		_Check("no_absolute_paths", "absolute-paths", "absolute-paths", lambda lines, text, path, tracked: check_absolute_paths(text, _python_string_lines(text) - _python_docstring_lines(text), path) if tracked else [], tracked_only=True),
	]

def _md_checks():
	from ._checks import (check_leading_blank,check_double_blank,check_absolute_paths,
		check_space_indent_exempt, check_trailing_whitespace, check_trailing_blank,
		check_final_newline, check_double_space)
	from ._markdown import (_frontmatter_exempt,_fence_exempt,_blockquote_exempt,_markdown_exempt_spans)

	def _abs_exempt(text):
		exempt = _frontmatter_exempt(text)
		exempt.update(_fence_exempt(text))
		exempt.update(_blockquote_exempt(text))
		return exempt

	def _space_exempt(text):
		exempt = _frontmatter_exempt(text)
		exempt.update(_fence_exempt(text))
		return exempt

	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_double_blank", "double-blank", "double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_absolute_paths", "absolute-paths", "absolute-paths", lambda lines, text, path, tracked: check_absolute_paths(text, _abs_exempt(text), path) if tracked else [], tracked_only=True),
		_Check("no_space_indent", "space-indent", "space-indent", lambda lines, text, path, tracked: check_space_indent_exempt(text, _space_exempt(text))),
		_Check("no_trailing", "trailing", "trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text, True)),
		_Check("no_final_newline", "final-newline", "final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
		_Check("no_double_space", "double-space", "double-space", lambda lines, text, path, tracked: check_double_space(text, False)),
	]

def _js_checks():
	from ._checks import (check_leading_blank,check_js_double_blank,check_js_space_indent,
		check_js_trailing_whitespace, check_js_trailing_blank, check_js_final_newline)
	from ._js import _js_exempt_lines

	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_js_double_blank", "js-double-blank", "js-double-blank", lambda lines, text, path, tracked: check_js_double_blank(text)),
		_Check("no_js_space_indent", "js-space-indent", "js-space-indent", lambda lines, text, path, tracked: check_js_space_indent(text, _js_exempt_lines(text))),
		_Check("no_js_trailing", "js-trailing", "js-trailing", lambda lines, text, path, tracked: check_js_trailing_whitespace(text)),
		_Check("no_js_final_newline", "js-final-newline", "js-final-newline", lambda lines, text, path, tracked: check_js_trailing_blank(text) + check_js_final_newline(lines)),
	]

def _html_checks():
	from ._checks import (check_leading_blank,check_double_blank,check_space_indent,
		check_trailing_whitespace, check_trailing_blank, check_final_newline)
	from . import _html

	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_html_double_blank", "html-double-blank", "html-double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_html_space_indent", "html-space-indent", "html-space-indent", lambda lines, text, path, tracked: check_space_indent(text)),
		_Check("no_html_trailing", "html-trailing", "html-trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text)),
		_Check("no_html_final_newline", "html-final-newline", "html-final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
		_Check("no_html_unclosed", "html-unclosed", "html-unclosed", lambda lines, text, path, tracked: _html.check_html(text)["unclosed"]),
		_Check("no_html_bad_closer", "html-bad-closer", "html-bad-closer", lambda lines, text, path, tracked: _html.check_html(text)["bad_closer"]),
		_Check("no_html_depth", "html-depth", "html-depth", lambda lines, text, path, tracked: _html.check_html(text)["depth"]),
	]

def _c_checks():
	from ._checks import (check_leading_blank,check_double_blank,check_space_indent,
		check_trailing_whitespace, check_trailing_blank, check_final_newline)

	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_double_blank", "double-blank", "double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_space_indent", "space-indent", "space-indent", lambda lines, text, path, tracked: check_space_indent(text)),
		_Check("no_trailing", "trailing", "trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text)),
		_Check("no_final_newline", "final-newline", "final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
	]

def build_language_checks():
	return {
		"py": _py_checks(),
		"md": _md_checks(),
		"js": _js_checks(),
		"html": _html_checks(),
		"c": _c_checks(),
	}

# Populated by _checks at import time (after its check functions are defined).
_LANGUAGE_CHECKS = None

__all__ = ['_JS_SUFFIXES', '_PY_MD_SUFFIXES', '_HTML_SUFFIXES', '_C_SUFFIXES', '_SH_SUFFIXES',
	'_ALL_SUFFIXES', '_SUFFIX_TO_LANGUAGE', '_Check', 'build_language_checks', '_LANGUAGE_CHECKS']
