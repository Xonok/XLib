#!/bin/sh
#
# Install git hooks from tools/hooks/ into the shared git directory.
#
# The hooks are symlinked, not copied: a change to one is live at once, with no
# install step, and the running hook cannot be older than the source.
#
# `pre-commit` is the exception. It is a regular file — the guard — because it
# is what checks that the other links resolve, and a link whose source is
# missing is a gate that does not run with nothing saying so. The guard reaches
# the style gate itself through tools/hooks/pre-commit.

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

# Where a link points, relative to the hooks directory when the shared git
# directory is the repository's own .git: a relative link survives the
# repository being moved, which an absolute one does not. A separate git
# directory is the exception, and there the link has to be absolute.
if [ "$COMMON_DIR" = "$REPO_ROOT/.git" ]; then
	LINK_BASE="../../tools/hooks"
else
	LINK_BASE="$HOOKS_SOURCE"
fi

echo "Installing git hooks..."

for hook in "$HOOKS_SOURCE"/*; do
	[ -f "$hook" ] || continue
	name=$(basename "$hook")
	case "$name" in
		# The installer is not a hook, and the guard and the style gate it
		# runs are installed by name below rather than linked.
		install.sh|pre-commit|pre-commit.guard) continue ;;
	esac
	target="$HOOKS_TARGET/$name"

	if [ -f "$target" ] && ! [ -L "$target" ]; then
		# Backup existing non-symlink hook
		mv "$target" "$target.backup.$(date +%s)"
		echo "  Backed up existing $name"
	fi

	# A link takes the mode of what it points at, so the source has to be
	# executable rather than the link.
	chmod +x "$hook"
	ln -sf "$LINK_BASE/$name" "$target"
	echo "  Linked $name"
done

# The guard is a regular file: it is what checks the links, so it cannot be one.
cp "$HOOKS_SOURCE/pre-commit.guard" "$HOOKS_TARGET/pre-commit"
chmod +x "$HOOKS_TARGET/pre-commit"
echo "  Installed pre-commit (the guard)"

# A link whose source is gone is a gate that does not run, and nothing says so.
# A source that is deliberately gone should take its link with it.
for target in "$HOOKS_TARGET"/*; do
	[ -L "$target" ] || continue
	if [ ! -e "$target" ]; then
		rm -f "$target"
		echo "  Removed stale link $(basename "$target")"
	fi
done

# Every link has to resolve. The guard would catch it at commit time, but a
# broken install is worth saying out loud now rather than at the next commit.
for target in "$HOOKS_TARGET"/*; do
	[ -L "$target" ] || continue
	if [ ! -e "$target" ]; then
		echo "ERROR: $target does not resolve" >&2
		exit 1
	fi
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
