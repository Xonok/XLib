import os
def path_in_scope(path,paths):
	for path_outer in paths:
		if path_in_path(path,path_outer): return True
	return False
def path_in_path(path,path_outer):
	if path.startswith("."): return False
	return path.startswith(path_outer)
def to_native(path):
	return os.path.normpath(os.path.abspath(path))
