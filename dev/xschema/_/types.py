from . import err

class Type:
	"""Base class for all types.

	Subclasses set `name` (the id used in notation) and implement
	`check(value, path)`, raising ValidationError on mismatch.
	"""
	name = None

	def check(self, value, path):
		raise NotImplementedError

	def __init__(self, *args):
		pass

	def __repr__(self):
		params = self._params()
		if params:
			inner = ", ".join("%s=%r" % (k, v) for k, v in params)
			return "%s(%s)" % (self.name, inner)
		return self.name

	def _params(self):
		return []

def parse(spec):
	"""Turn a type spec into a Type instance.

	Accepts a type id string (`"int"`, `"int_nat"`, `"list:int(0,5)"`,
	`"dict:str:int"`), a python builtin (`int`, `str`, ...), an existing Type,
	or a composite dict (`{"name": "str", "?email": "str"}`).
	"""
	if isinstance(spec, Type):
		return spec
	if isinstance(spec, dict):
		return CompositeType(_composite_fields(spec))
	if isinstance(spec, type):
		cls = _PY_BUILTINS.get(spec)
		if cls is not None:
			return cls()
		raise ValueError("unsupported python type %r" % (spec,))
	if isinstance(spec, str):
		return _parse_string(spec)
	raise ValueError("cannot interpret type spec %r" % (spec,))

def _composite_fields(spec):
	fields = {}
	for key, val in spec.items():
		optional = False
		if key.startswith("?"):
			optional = True
			key = key[1:]
		fields[key] = (parse(val), optional)
	return fields

def _parse_string(spec):
	spec = spec.strip()
	if ":" in spec:
		head, tail = spec.split(":", 1)
	else:
		head, tail = spec, None
	base, params = _split_seg(head)
	kwargs = _bounds_kwargs(base, params)
	if tail is not None:
		if base == "list":
			return ListType(elem=parse(tail), **kwargs)
		if base == "dict":
			if ":" in tail:
				key_part, value_part = tail.split(":", 1)
				return DictType(key=parse(key_part), value=parse(value_part))
			return DictType(key=parse(tail))
		raise ValueError("type %r is not a container" % base)
	return _construct(base, kwargs)

def _bounds_kwargs(base, params):
	if base in ("dict", "bool"):
		if params:
			raise ValueError("%s takes no bounds" % base)
		return {}
	if base == "list":
		lo, hi = _bounds(params, "list")
		return {"lo": lo, "hi": hi}
	lo, hi = _bounds(params, base)
	return {"lo": lo, "hi": hi}

def _construct(base, kwargs):
	cls = REGISTRY.get(base)
	if cls is None:
		raise ValueError("unknown type %r" % base)
	return cls(**kwargs)

def _split_seg(seg):
	if "(" not in seg:
		return seg, ()
	base = seg[:seg.index("(")]
	tail = seg[seg.index("(")+1:]
	if not tail.endswith(")"):
		raise ValueError("unbalanced parens in %r" % seg)
	inside = tail[:-1].strip()
	params = _split_params(inside) if inside else ()
	return base, params

def _split_params(inside):
	out = []
	for item in inside.split(","):
		item = item.strip()
		if not item:
			raise ValueError("empty parameter in %r" % inside)
		out.append(_coerce(item))
	return out

def _coerce(item):
	lower = item.lower()
	if lower == "true":
		return True
	if lower == "false":
		return False
	if lower in ("none", "null"):
		return None
	try:
		return int(item)
	except ValueError:
		pass
	try:
		return float(item)
	except ValueError:
		pass
	return item

def _bounds(args, kind, max_args=2):
	if len(args) > max_args:
		raise ValueError("%s accepts at most %d bounds" % (kind, max_args))
	if not args:
		return (None, None)
	if len(args) == 1:
		return (None, args[0])
	return (args[0], args[1])

def _bound_check(kind, lo, hi):
	if lo is not None and hi is not None and lo > hi:
		raise ValueError("invalid %s range %s..%s" % (kind, lo, hi))

class IntType(Type):
	name = "int"
	_lo = None
	_hi = None

	def __init__(self, lo=None, hi=None):
		if lo is None:
			lo = getattr(type(self), "_lo", None)
		if hi is None:
			hi = getattr(type(self), "_hi", None)
		self._lo, self._hi = lo, hi
		_bound_check("int", self._lo, self._hi)

	def check(self, value, path):
		if isinstance(value, bool) or not isinstance(value, int):
			raise err.ValidationError(path, "expected integer, got %s" % type(value).__name__)
		if self._lo is not None and value < self._lo:
			raise err.ValidationError(path, "expected integer >= %s, got %s" % (self._lo, value))
		if self._hi is not None and value > self._hi:
			raise err.ValidationError(path, "expected integer <= %s, got %s" % (self._hi, value))

	def _params(self):
		return [("lo", self._lo), ("hi", self._hi)]

class IntNat(IntType):
	name = "int_nat"
	_lo = 0

class IntGt0(IntType):
	name = "int_gt0"
	_lo = 1

class FloatType(Type):
	name = "float"

	def __init__(self, lo=None, hi=None):
		self._lo, self._hi = lo, hi
		_bound_check("float", self._lo, self._hi)

	def check(self, value, path):
		if isinstance(value, bool) or not isinstance(value, (int, float)):
			raise err.ValidationError(path, "expected float, got %s" % type(value).__name__)
		if self._lo is not None and value < self._lo:
			raise err.ValidationError(path, "expected float >= %s, got %s" % (self._lo, value))
		if self._hi is not None and value > self._hi:
			raise err.ValidationError(path, "expected float <= %s, got %s" % (self._hi, value))

	def _params(self):
		return [("lo", self._lo), ("hi", self._hi)]

class NumType(Type):
	name = "num"

	def __init__(self, lo=None, hi=None):
		self._lo, self._hi = lo, hi
		_bound_check("num", self._lo, self._hi)

	def check(self, value, path):
		if isinstance(value, bool) or not isinstance(value, (int, float)):
			raise err.ValidationError(path, "expected number, got %s" % type(value).__name__)
		if self._lo is not None and value < self._lo:
			raise err.ValidationError(path, "expected number >= %s, got %s" % (self._lo, value))
		if self._hi is not None and value > self._hi:
			raise err.ValidationError(path, "expected number <= %s, got %s" % (self._hi, value))

	def _params(self):
		return [("lo", self._lo), ("hi", self._hi)]

class BoolType(Type):
	name = "bool"

	def check(self, value, path):
		if not isinstance(value, bool):
			raise err.ValidationError(path, "expected boolean, got %s" % type(value).__name__)

class StrType(Type):
	name = "str"

	def __init__(self, lo=None, hi=None):
		self._lo, self._hi = lo, hi
		_bound_check("str", self._lo, self._hi)

	def check(self, value, path):
		if not isinstance(value, str):
			raise err.ValidationError(path, "expected string, got %s" % type(value).__name__)
		if self._lo is not None and len(value) < self._lo:
			raise err.ValidationError(path, "expected string length >= %s, got %s" % (self._lo, len(value)))
		if self._hi is not None and len(value) > self._hi:
			raise err.ValidationError(path, "expected string length <= %s, got %s" % (self._hi, len(value)))

	def _params(self):
		return [("lo", self._lo), ("hi", self._hi)]

class ListType(Type):
	name = "list"

	def __init__(self, elem=None, lo=None, hi=None):
		self.elem = elem
		self._lo, self._hi = lo, hi
		_bound_check("list", self._lo, self._hi)

	def check(self, value, path):
		if not isinstance(value, list):
			raise err.ValidationError(path, "expected list, got %s" % type(value).__name__)
		n = len(value)
		if self._lo is not None and n < self._lo:
			raise err.ValidationError(path, "expected list length >= %s, got %s" % (self._lo, n))
		if self._hi is not None and n > self._hi:
			raise err.ValidationError(path, "expected list length <= %s, got %s" % (self._hi, n))
		if self.elem is not None:
			for i, item in enumerate(value):
				self.elem.check(item, path + [i])

	def _params(self):
		return [("lo", self._lo), ("hi", self._hi)]

class DictType(Type):
	name = "dict"

	def __init__(self, key=None, value=None):
		self.key = key
		self.value = value

	def check(self, value, path):
		if not isinstance(value, dict):
			raise err.ValidationError(path, "expected dict, got %s" % type(value).__name__)
		if self.key is not None or self.value is not None:
			for k, v in value.items():
				if self.key is not None:
					self.key.check(k, path + [k])
				if self.value is not None:
					self.value.check(v, path + [k])

class CompositeType(Type):
	name = "composite"

	def __init__(self, fields):
		self.fields = fields

	def check(self, value, path):
		if not isinstance(value, dict):
			raise err.ValidationError(path, "expected dict, got %s" % type(value).__name__)
		for key, (ftype, optional) in self.fields.items():
			if key not in value:
				if optional:
					continue
				raise err.ValidationError(path, "missing required field %r" % key)
			ftype.check(value[key], path + [key])
		for key in value:
			if key not in self.fields:
				raise err.ValidationError(path, "unexpected field %r" % key)

	def _params(self):
		return [("fields", dict(self.fields))]

class Registry:
	"""Maps type id strings to Type classes. User types register here."""

	def __init__(self):
		self._types = {}

	def register(self, cls):
		if not cls.name:
			raise ValueError("type class %r has no name" % (cls,))
		self._types[cls.name] = cls
		return cls

	def get(self, name):
		return self._types.get(name)

	def __getitem__(self, name):
		return self._types[name]

	@property
	def names(self):
		return sorted(self._types)

REGISTRY = Registry()
for _cls in (IntType, IntNat, IntGt0, FloatType, NumType, BoolType, StrType, ListType, DictType):
	REGISTRY.register(_cls)

_PY_BUILTINS = {
	int: IntType,
	str: StrType,
	bool: BoolType,
	float: FloatType,
}

def validate(value, spec):
	"""Validate `value` against a type spec. Returns None on success, else raises."""
	return parse(spec).check(value, [])
