class CSVError(Exception):
	pass

class ParseError(CSVError):
	pass

class SchemaError(CSVError):
	pass

class UnfinishedLineError(CSVError):
	pass

class IOError(CSVError):
	pass

class ReschemaError(CSVError):
	pass
