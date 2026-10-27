"""The project's own exceptions.

Kept in one small module so the importers and the domain can raise the same types without
importing each other.
"""

class StockError(Exception):
	"""Base class for the project's own errors."""

class UnknownSku(StockError):
	"""Raised when a lookup names a SKU that is not in the book."""
