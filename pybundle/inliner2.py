"""
First process each file separately.
Look at imports, figure out their full path.
Replace each thing from an imported file with its full path, except underscores instead of dots.
What to do about folder imports? Treat __init__py as a file without a name. I.e. don't use that as the "module name" of anything in it, but do use the path before it.
"""
#def inline(fpath_in,fpath_out):
	#lines = file.open(fpath_in,"r",encoding="UTF-8").readlines()

import sys,os

def main():
	fpath_in,fpath_out = parse_cmd_args()
	process(fpath_in,fpath_out)
def parse_cmd_args():
	args = sys.argv()
	if len(args) < 2:
		raise Exception("Need at least 2 commandline arguments: fpath_in and fpath_out")
	if len(args) > 2:
		raise Exception("Too many arguments. The commandline format is: fpath_in fpath_out")
	return args[0],args[1]
def process(fpath_in,fpath_out):
	files = {}
	root = get_root(fpath_in)
	#CONFLICT: get_file_data has unclear purpsoe
	file = get_file_data(fpath_in)
	while(file):
		file = process_file(fpath_in,root,files)
	combine_files(files)
def get_root(fpath_in):
	return os.path.dirname(fpath_in)
def process_file(fpath_in,root,files):
	modpath = resolve_modpath(fpath_in)
	lines = get_file_data(fpath_in)
	local_imports = process_imports(lines,files)
	nodes = python_parse(lines)
	for node in nodes:
		if node.rootname in local_imports:
			node.rootname = local_imports[node.rootname]
	files[modpath] = nodes
def python_parse(lines):
	nodes = []
	for line in lines:
		tokens = python_tokenize(line)
		

process("../../Space-Traveller/server.py","traveller.py")
