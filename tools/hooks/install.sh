#!/bin/sh
#
# Install git hooks from tools/hooks/ into the shared git directory.

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_SOURCE="$REPO_ROOT/tools/hooks"

# The hooks belong in the shared git directory: that is where git looks, from the
# main checkout and from every worktree alike. A worktree's own git directory is
# not that one, and a relative `core.hooksPath` resolves inside the worktree,
# where `.git` is a file rather than a directory — so the hooks do not run there
# and nothing says so.
COMMON_DIR=$(cd "$(git rev-parse --git-common-dir)" && pwd)
HOOKS_TARGET="$COMMON_DIR/hooks"

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

# `core.hooksPath` is left at git's default, which finds the directory above
# from a worktree as well as from the main checkout. The relative value this
# script used to write is what silenced the hooks inside a worktree, so it goes
# when it is still there.
if [ "$(git config --get core.hooksPath || true)" = ".git/hooks" ]; then
	git config --unset core.hooksPath
	echo "Removed the relative core.hooksPath; git finds $HOOKS_TARGET from a worktree too"
fi

echo "Done. Hooks installed to $HOOKS_TARGET"