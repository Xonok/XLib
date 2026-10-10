#!/bin/sh
#
# Install git hooks from tools/hooks/ into .git/hooks/

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_SOURCE="$REPO_ROOT/tools/hooks"

# Find the git directory (works for both regular repos and worktrees)
GIT_DIR=$(git rev-parse --git-dir)
HOOKS_TARGET="$GIT_DIR/hooks"

if [ ! -d "$HOOKS_SOURCE" ]; then
	echo "ERROR: hooks source directory not found: $HOOKS_SOURCE"
	exit 1
fi

if [ ! -d "$HOOKS_TARGET" ]; then
	echo "ERROR: hooks target directory not found: $HOOKS_TARGET"
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

# Set core.hooksPath to use the worktree's hooks directory
git config core.hooksPath "$HOOKS_TARGET"

echo "Done. Hooks installed to $HOOKS_TARGET"
echo "core.hooksPath set to $HOOKS_TARGET"