import json,os

_UNSET = object()
_DEFAULT_BASE = "config"

_data = {}
_policies = {}
_base = _DEFAULT_BASE

def configure(base):
	global _base
	_base = base

def merge(defs, over):
	if isinstance(defs, dict) and isinstance(over, dict):
		out = dict(defs)
		for k, v in over.items():
			out[k] = merge(out.get(k), v)
		return out
	return over

def difference(defs, over):
	if isinstance(defs, dict) and isinstance(over, dict):
		res = {}
		for k, v in over.items():
			if k not in defs:
				res[k] = v
				continue
			d = difference(defs[k], v)
			if d is not _UNSET:
				res[k] = d
		return res or _UNSET
	if defs != over:
		return over
	return _UNSET

def missing(defs, over):
	miss = []
	if isinstance(defs, dict) and isinstance(over, dict):
		for k, v in defs.items():
			if k not in over:
				miss.append(k)
			else:
				for sub in missing(v, over[k]):
					miss.append(f"{k}.{sub}")
	return miss

def _paths(name, default=False):
	rdir = os.path.join(_base, "default") if default else _base
	return os.path.join(rdir, name + ".json")

def read_json(path):
	with open(path, "r") as f:
		return json.load(f)

def write_json(name, data):
	with open(_paths(name), "w") as f:
		json.dump(data, f, indent="\t")

def _handle_omissions(name, override, default, policy):
	miss = missing(default, override)
	if not miss:
		return override
	if policy == "fill":
		filled = merge(default, override)
		write_json(name, filled)
		return filled
	msg = f"config '{name}' is missing key(s): {', '.join(miss)}"
	raise ValueError(msg)

def _read_one(name, policy):
	user_path = _paths(name)
	try:
		default_path = _paths(name, default=True)
		with open(default_path, "r") as f:
			default = json.load(f)
	except FileNotFoundError:
		msg = f"no default config for '{name}' at {default_path}"
		raise ValueError(msg) from None
	if not os.path.isfile(user_path):
		write_json(name, default)
		return dict(default)
	override = read_json(user_path)
	if policy is not None:
		return _handle_omissions(name, override, default, policy)
	return override

def read(name, policy=None):
	if policy is None:
		policy = _policies.get(name)
	result = _read_one(name, policy)
	_data[name] = result
	return result

def read_all():
	count = 0
	for fname in os.listdir(os.path.join(_base, "default")):
		if not fname.endswith(".json"):
			continue
		root = fname[:-5]
		read(root, _policies.get(root))
		count += 1
	return count

def get(name):
	return _data.get(name)

def no_omissions(name, strict=False):
	_policies[name] = "strict" if strict else "fill"

def save(name, data, diff_only=False):
	with open(_paths(name, default=True), "r") as f:
		default = json.load(f)
	content = difference(default, data) if diff_only else data
	if content is _UNSET:
		content = {}
	write_json(name, content)
