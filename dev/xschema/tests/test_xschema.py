from xschema.xschema import BoolType,CompositeType,DictType,FloatType,IntGt0,IntNat,IntType,ListType,NumType,Schema,StrType,Type,ValidationError,format_path,parse,validate
from xlib import xtest

def test_simple_int():
	validate(3, "int")
	validate(0, "int")
	validate(-5, "int")

def test_simple_int_rejects_bool():
	xtest.raises(ValidationError, lambda: validate(True, "int"))

def test_simple_int_rejects_str():
	xtest.raises(ValidationError, lambda: validate("3", "int"))

def test_int_nat_non_negative():
	validate(0, "int_nat")
	validate(7, "int_nat")
	xtest.raises(ValidationError, lambda: validate(-1, "int_nat"))

def test_int_gt0_positive():
	validate(1, "int_gt0")
	validate(999, "int_gt0")
	xtest.raises(ValidationError, lambda: validate(0, "int_gt0"))
	xtest.raises(ValidationError, lambda: validate(-3, "int_gt0"))

def test_int_range():
	validate(50, "int(0,100)")
	validate(0, "int(0,100)")
	validate(100, "int(0,100)")
	xtest.raises(ValidationError, lambda: validate(-1, "int(0,100)"))
	xtest.raises(ValidationError, lambda: validate(101, "int(0,100)"))

def test_int_max_only():
	validate(5, "int(10)")
	xtest.raises(ValidationError, lambda: validate(11, "int(10)"))

def test_int_nat_with_hi():
	validate(5, "int_nat(10)")
	xtest.raises(ValidationError, lambda: validate(-1, "int_nat(10)"))
	xtest.raises(ValidationError, lambda: validate(11, "int_nat(10)"))

def test_float():
	validate(3.5, "float")
	validate(3, "float")
	xtest.raises(ValidationError, lambda: validate("3.5", "float"))

def test_num_accepts_int_and_float():
	validate(3, "num")
	validate(3.5, "num")
	xtest.raises(ValidationError, lambda: validate("3", "num"))

def test_bool():
	validate(True, "bool")
	validate(False, "bool")
	xtest.raises(ValidationError, lambda: validate(1, "bool"))
	xtest.raises(ValidationError, lambda: validate("yes", "bool"))

def test_str():
	validate("hello", "str")
	validate("", "str")
	xtest.raises(ValidationError, lambda: validate(42, "str"))

def test_str_length():
	validate("ab", "str(3)")
	xtest.raises(ValidationError, lambda: validate("abcd", "str(3)"))
	validate("abc", "str(1,3)")
	xtest.raises(ValidationError, lambda: validate("", "str(1,3)"))

def test_list():
	validate([], "list")
	validate([1, 2, 3], "list")

def test_list_rejects_non_list():
	xtest.raises(ValidationError, lambda: validate((1, 2), "list"))

def test_list_length_bounds():
	validate([1, 2], "list(1,3)")
	xtest.raises(ValidationError, lambda: validate([], "list(1,3)"))
	xtest.raises(ValidationError, lambda: validate([1, 2, 3, 4], "list(1,3)"))

def test_list_of_int():
	validate([1, 2, 3], "list:int")
	xtest.raises(ValidationError, lambda: validate([1, "two"], "list:int"))

def test_list_of_int_with_elem_range():
	validate([1, 2], "list:int(0,5)")
	xtest.raises(ValidationError, lambda: validate([1, 9], "list:int(0,5)"))

def test_nested_list():
	validate([[1], [2, 3]], "list:list:int")
	xtest.raises(ValidationError, lambda: validate([[1], ["x"]], "list:list:int"))

def test_dict():
	validate({}, "dict")
	validate({"a": 1}, "dict")

def test_dict_str_int():
	validate({"a": 1, "b": 2}, "dict:str:int")
	xtest.raises(ValidationError, lambda: validate({"a": 1, 2: 2}, "dict:str:int"))
	xtest.raises(ValidationError, lambda: validate({"a": "x"}, "dict:str:int"))

def test_dict_values_list_int():
	validate({"a": [1, 2]}, "dict:str:list:int")
	xtest.raises(ValidationError, lambda: validate({"a": [1, "x"]}, "dict:str:list:int"))

def test_composite():
	t = parse({"name": "str", "age": "int"})
	validate({"name": "bob", "age": 3}, t)
	xtest.raises(ValidationError, lambda: validate({"name": "bob"}, t))
	xtest.raises(ValidationError, lambda: validate({"name": "bob", "age": "old"}, t))
	xtest.raises(ValidationError, lambda: validate({"name": "bob", "age": 3, "extra": 1}, t))

def test_composite_optional():
	t = parse({"name": "str", "?email": "str"})
	validate({"name": "bob"}, t)
	validate({"name": "bob", "email": "b@x.com"}, t)
	xtest.raises(ValidationError, lambda: validate({"name": "bob", "email": 42}, t))

def test_parse_returns_same_instance():
	t = parse("int")
	xtest.same(parse(t), t)

def test_parse_python_builtin():
	validate(3, int)
	validate("hi", str)
	validate(1.5, float)
	validate(True, bool)

def test_unknown_type_raises():
	xtest.raises(ValueError, lambda: parse("nope"))

def test_validation_error_path():
	t = parse({"person": {"name": "str", "age": "int"}})
	try:
		validate({"person": {"name": "bob", "age": "old"}}, t)
	except ValidationError as e:
		xtest.equal(e.path_str, "person.age")
		xtest.equal(e.path, ["person", "age"])

def test_list_error_path():
	t = parse("list:list:int")
	try:
		validate([[1], [2, "x"]], t)
	except ValidationError as e:
		xtest.equal(e.path_str, "[1][1]")
		xtest.equal(e.path, [1, 1])

def test_format_path():
	xtest.equal(format_path(["a", 0, "b"]), "a[0].b")
	xtest.equal(format_path([0, 1]), "[0][1]")

def test_registry_contains_builtins():
	for name in ("int", "int_nat", "int_gt0", "float", "num", "bool", "str", "list", "dict"):
		xtest.true(parse(name) is not None)

def test_custom_type():
	class Even(IntType):
		name = "even"

		def check(self, value, path):
			super().check(value, path)
			if value % 2 != 0:
				raise ValidationError(path, "expected even integer, got %s" % value)

	from xschema.xschema import REGISTRY
	REGISTRY.register(Even)
	validate(4, "even")
	xtest.raises(ValidationError, lambda: validate(3, "even"))

def test_subclass_default_change():
	validate(0, "int_nat")
	xtest.raises(ValidationError, lambda: validate(-1, "int_nat"))

def test_schema_from_function_defaults():
	def greet(name: str, age=5, active=True):
		return "%s:%d:%s" % (name, age, active)

	from xschema.xschema import Schema
	schema = Schema.from_function(greet)
	xtest.true("name" in schema.fields)
	schema.check({"name": "bob", "age": 3, "active": False})
	xtest.raises(ValidationError, lambda: schema.check({"name": "bob", "age": "old"}))

def test_schema_decorator_validates():
	from xschema.xschema import Schema

	def add(a: int, b: int = 5):
		return a + b

	validated = Schema.from_function(add).validate(add)
	xtest.equal(validated(3), 8)
	xtest.equal(validated(3, 4), 7)
	xtest.raises(ValidationError, lambda: validated("x", 2))
