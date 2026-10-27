"""Where the project's data files live.

This module sits in `stockroom/config/`, so the project root is three directories up from
this file. Before the modules were grouped into packages it was one directory down; the
move is why the walk is written in terms of the package's own location rather than the
process's working directory.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def data_dir():
	return os.path.join(ROOT,"stockroom","data")

def data_file(name):
	return os.path.join(data_dir(),name)
