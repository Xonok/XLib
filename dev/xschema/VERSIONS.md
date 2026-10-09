# Xschema version history

> **Convention:** each entry cites the epiq ref of the release's ticket (e.g. `[ABC1234]`). Entries without a ref were released before this convention.

## 1_0_0

Initial release of the xschema library.

Public API: validate, parse, Registry, Type and the concrete type classes
(IntType, FloatType, NumType, BoolType, StrType, ListType, DictType,
CompositeType), plus ValidationError. Defines and validates values against
string-based type specs.
