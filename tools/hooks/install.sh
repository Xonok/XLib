#!/bin/sh
#
# Install git hooks from tools/hooks/ into .git/hooks/

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_SOURCE="$REPO_ROOT/tools/hooks"
HOOKS_TARGET="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_SOURCE" ]; then
	echo "ERROR: hooks source directory not found: $HOOKS_SOURCE"
	exit 1
fi

if [ ! -d "$HOOKS_TARGET" ]; then
	echo "ERROR: .git/hooks directory not found. Are you in a git repository?"
	exit 1
fi

echo "Installing git hooks..."

for hook in "$HOOKS_SOURCE"/*; do
	[ -f "$hook" ] || continue
	name=$(basename "$hook")
	target="$HOOKS_TARGET/$name"

	if [ -f "$target" ] && ! [ -L "$target" ]; then
		# Backup existing non-symlink hook
		mv "$target" "$target.backup.$(date +%s)"
		echo "  Backed up existing $name"
	fi

	cp "$hook" "$target"
	chmod +x "$target"
	echo "  Installed $name"
done

echo "Done. Hooks installed to $HOOKS_TARGET"