"""xschema — runtime type and schema validation against type specifications.

One `parse()` funnel accepts two equivalent expression forms: the compact string
notation (`"int"`, `"int_nat"`, `"list:int(0,5)"`, `"dict:str:int"`) and the
Python form (builtins, `Type` instances, composite dicts like
`{"name": "str", "?email": "str"}`). Both produce `Type` instances with a shared
`check(value, path)` contract, and `Schema.from_function()` builds a schema from
a function's annotations and defaults so every call to it can be validated.

This file is the public interface and nothing else: the implementation lives in
`_/`, as err (the exception type and the path formatter), types (the type
hierarchy, the parse funnel and the registry) and schema (the function-signature
schema and its decorator). The classes are bound here under the names this
library publishes, and the three functions are thin wrappers over their internal
counterparts.
"""
from ._ import err,schema,types

#The public names, bound to their definitions in _/ so the bundler's prefix
#cannot take them away from the caller.
Type = types.Type
IntType = types.IntType
IntNat = types.IntNat
IntGt0 = types.IntGt0
FloatType = types.FloatType
NumType = types.NumType
BoolType = types.BoolType
StrType = types.StrType
ListType = types.ListType
DictType = types.DictType
CompositeType = types.CompositeType
Registry = types.Registry
REGISTRY = types.REGISTRY
Schema = schema.Schema
SchemaDecorator = schema.SchemaDecorator
ValidationError = err.ValidationError

def parse(spec: str | type | Type | dict) -> Type:
	"""Turn a type spec into a `Type` instance."""
	return types.parse(spec)

def validate(value: object, spec: str | type | Type | dict) -> None:
	"""Validate `value` against a type spec; raises `ValidationError` on mismatch."""
	return types.validate(value, spec)

def format_path(path: list) -> str:
	"""Format a path list as a dotted locator (`user.addresses[0].zip`)."""
	return err.format_path(path)
