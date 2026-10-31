#!/usr/bin/env python3
"""xlint — the repository's style checker.

Package entry point. The implementation lives in the sibling modules; this file
re-exports their names so existing callers (`xlint <paths>`, tests importing
`tools.xlint.xlint`) keep working.
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

try:
	from ._io import *
	from . import _io
except ImportError:
	from _io import *
	import _io
try:
	from ._repo_rules import *
except ImportError:
	from _repo_rules import *
try:
	from ._checks import *
except ImportError:
	from _checks import *
try:
	from ._markdown import *
except ImportError:
	from _markdown import *
try:
	from ._python import *
except ImportError:
	from _python import *
try:
	from ._js import *
except ImportError:
	from _js import *
try:
	from . import _html
except ImportError:
	import _html
try:
	from . import _personal
except ImportError:
	import _personal
try:
	from . import _banned_git
except ImportError:
	import _banned_git
try:
	from . import _c
except ImportError:
	import _c
try:
	from ._watch import *
	from . import _watch
except ImportError:
	from _watch import *
	import _watch
try:
	from ._cli import *
except ImportError:
	from _cli import *

if __name__ == "__main__":
	sys.exit(main())
