import functools,inspect
from . import err,types

def _simple_from_annotation(annotation):
	if isinstance(annotation, types.Type):
		return annotation
	if isinstance(annotation, str):
		return types.parse(annotation)
	if isinstance(annotation, dict):
		return types.parse(annotation)
	if isinstance(annotation, type):
		cls = types._PY_BUILTINS.get(annotation)
		if cls is not None:
			return cls()
		raise ValueError("unsupported annotation %r" % (annotation,))
	raise ValueError("unsupported annotation %r" % (annotation,))

def _type_from_default(default):
	if inspect.isclass(default):
		raise ValueError("default is a class, cannot infer type")
	if isinstance(default, bool):
		return types.BoolType()
	if isinstance(default, int):
		return types.IntType()
	if isinstance(default, float):
		return types.FloatType()
	if isinstance(default, str):
		return types.StrType()
	if isinstance(default, list):
		return types.ListType()
	if isinstance(default, dict):
		return types.DictType()
	raise ValueError("cannot infer type from default %r" % (default,))

class Schema:
	"""Describes a function's parameters, built from annotations and defaults.

	`Schema.from_function(fn)` inspects `fn`; the resulting schema can validate
	a call's arguments via `check`. Used as a decorator (`@schema.validate`) it
	wraps a function so every call is validated against the described types.
	"""

	def __init__(self, fn, fields):
		self.fn = fn
		self.fields = fields

	@classmethod
	def from_function(cls, fn):
		fields = _fields_from_signature(inspect.signature(fn))
		return cls(fn, fields)

	def validate(self, fn=None):
		"""Decorator: wrap `fn` so calls are validated against this schema."""
		if fn is None:
			return SchemaDecorator(self)
		return SchemaDecorator(self)(fn)

	def check(self, argdict, path=()):
		for name, (ftype, optional) in self.fields.items():
			if name not in argdict:
				if optional:
					continue
				raise err.ValidationError(list(path), "missing required param %r" % name)
			ftype.check(argdict[name], list(path) + [name])

	def bind(self, args, kwargs):
		argdict = {}
		names = list(self.fields)
		for i, value in enumerate(args):
			if i < len(names):
				argdict[names[i]] = value
		for name, value in kwargs.items():
			if name not in self.fields:
				raise err.ValidationError([], "unexpected param %r" % name)
			argdict[name] = value
		return argdict

class SchemaDecorator:
	"""Wraps a function so each call is validated against the schema."""

	def __init__(self, schema):
		self.schema = schema

	def __call__(self, fn):
		schema = self.schema
		user = fn

		@functools.wraps(fn)
		def wrapped(*args, **kwargs):
			argdict = schema.bind(args, kwargs)
			schema.check(argdict)
			return user(*args, **kwargs)

		return wrapped

def _fields_from_signature(sig):
	fields = {}
	for name, param in sig.parameters.items():
		if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
			continue
		if param.default is not inspect.Parameter.empty:
			ftype = _type_from_default(param.default)
			optional = True
		elif param.annotation is not inspect.Parameter.empty:
			ftype = _simple_from_annotation(param.annotation)
			optional = False
		else:
			raise ValueError("param %r has no type annotation or default" % name)
		fields[name] = (ftype, optional)
	return fields
