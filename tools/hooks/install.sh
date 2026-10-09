#!/bin/sh
# Install the xlint pre-commit hook via core.hooksPath.

set -eu

root=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$root" ]; then
	echo "install-hooks: not a git repository" >&2
	exit 1
fi

hooks_dir="$root/tools/hooks"
if [ ! -d "$hooks_dir" ]; then
	echo "install-hooks: $hooks_dir not found" >&2
	exit 1
fi

git config core.hooksPath "$hooks_dir"
chmod +x "$hooks_dir/pre-commit"
echo "xlint pre-commit hook installed at $hooks_dir/pre-commit"
echo "To uninstall: git config --unset core.hooksPath"