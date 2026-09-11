# Test for different indentation scenarios
def public_function():
    """Module-level function - should be flagged"""
    pass

def public_function_with_return() -> str:
    """Module-level function with return type - should pass"""
    return "test"

def _private_function():
    """Private function - should be skipped"""
    pass

def public_function_at_indent():
    """Function with leading spaces - edge case"""
    pass

def   function_with_multiple_spaces():  # Edge case - multiple spaces
    """Function with multiple leading spaces - should still be detected"""
    pass