#!/bin/sh
# Run the xhttp test suite, passing all arguments to the test runner.
#
# Usage:
#   ./test_xhttp.sh           # run all tests
#   ./test_xhttp.sh --core    # skip edge tests
#   ./test_xhttp.sh -v        # verbose (passed to unittest)

cd "$(dirname "$0")/test" && python3 run.py "$@"