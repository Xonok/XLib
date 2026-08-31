import re,importlib.util,types,os,sys

def get_module_path(module_name,package=None):
	spec = importlib.util.find_spec(module_name)
	if spec is None or spec.origin is None:
		raise ImportError(f"Cannot find source for {module_name!r}")
	return spec.origin
inline_func="""import types
def inline(source,name):
	mod = types.ModuleType(name)
	mod.__file__ = f"<{name}>"
	exec(source, mod.__dict__)
	return mod
"""
def get_module_data(path):
	data = open(path,"r",encoding="UTF-8").read()
	if not data.endswith("\n"):
		data += "\n"
	data += "\n"
	return data
modules = {}
skipped = {}
def get_package(path):
	global root_dir
	path_dir = os.path.dirname(path)
	if not path_dir.startswith(root_dir): return ""
	path = os.path.dirname(path)
	path_inner = path[len(root_dir):]
	if path_inner.startswith(os.path.sep):
		path_inner = path_inner[len(os.path.sep):]
	return ".".join(path_inner.split(os.path.sep))
def process(fpath_in,imported,lines_out,package=None):
	fpath_in_folder = os.path.dirname(fpath_in)
	lines_in = []
	with open(fpath_in,"r",encoding="UTF-8") as f:
		lines_in = f.readlines()
	for line in lines_in:
		stripped = line.strip()
		tokens = stripped.split(" ")
		if len(tokens) == 0: continue
		source = ""
		names = []
		if tokens[0] == "from":
			source = tokens[1]
			names = tokens[3].split(",")
		if tokens[0] == "import":
			names = tokens[1].split(",")
		if len(names):
			if source == ".":
				source = get_package(fpath_in)
			for name in names:
				local_lines_out = []
				name = name.strip()
				fullname = source+"."+name if source else name
				if fullname in modules: continue
				if fullname in skipped: continue
				try:
					path = get_module_path(fullname)
					get_package(path)
				except ModuleNotFoundError:
					print("Didn't find result for: "+source+" "+name)
					skipped[fullname] = True
					continue
				except ImportError as e:
					print("Didn't find source for: "+name+" in "+source)
					skipped[fullname] = True
					continue
				if root_dir not in path and "xlib" not in source:
					print("Skipping "+fullname+" because it's inbuilt.")
					skipped[fullname] = True
					continue
				modules[fullname] = True
				subpackage = source+"."+name
				process(path,imported,local_lines_out,subpackage)
				code = "".join(local_lines_out)
				imported.append((name,code))
			continue
		lines_out.append(line)
root_dir = None
def inline(fpath_in,fpath_out):
	global root_dir
	#relative paths break imports, so need it absolute
	fpath_in = os.path.abspath(fpath_in)
	fpath_folder = os.path.dirname(fpath_in)
	root_dir = fpath_folder
	cwd = os.getcwd()
	os.chdir(fpath_folder)
	sys.path.insert(0,fpath_folder)
	imported = []
	lines_out = []
	process(fpath_in,imported,lines_out)
	os.chdir(cwd)
	with open(fpath_out,"w",encoding="UTF-8") as f:
		f.write(inline_func)
		for data in imported:
			name,code = data
			f.write("#import "+name+"\n")
			f.write(name+"_code = \"\"\"\n")
			f.write(code)
			f.write("\"\"\"\n")
			f.write(name+" = inline("+name+"_code,\""+name+"\")\n\n")
		for line in lines_out:
			f.write(line)
	print("Imported",len(imported))
	print("Modules",len(modules))
#inline("../xlib_legacy/frac.py","frac2.py")
inline("../../Space-Traveller/server.py","traveller.py")
def test(fpath_in):
	fpath_in = os.path.abspath(fpath_in)
	fpath_folder = os.path.dirname(fpath_in)
	os.chdir(fpath_folder)
	sys.path.insert(0,fpath_folder)
	print(fpath_folder)
	print(get_module_path("defs","server"))
	print(get_module_path("enemies","server.Analysis"))
#test("../../Space-Traveller/server.py")