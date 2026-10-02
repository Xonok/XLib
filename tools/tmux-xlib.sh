#!/bin/bash
# tmux-xlib.sh — the four-pane work panel, for any repository on this box.
#
# One implementation, no per-repo copy: the launchers pass the repo, or point
# at a directory inside it and let the git-root walk-up find it. Which pane
# runs where is spelled out under the usage.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XLIB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
	cat <<'EOF'
Usage: tmux-xlib.sh [REPO_PATH] [SESSION_NAME]

  REPO_PATH     any directory inside the target repo; its git root is what
                gets used, so a launcher sitting in tools/ still means the
                repo. Omitted: the git root above the cwd. Outside any repo
                with no argument: XLib.
  SESSION_NAME  overrides the name derived from the path.

Panes: xlint and taskview run in the target repo, skynet anywhere, marduk in
XLib. The repo's .taskview.yaml is found by walking up from the working
directory, so the cwd is what filters the taskview pane — not a flag.
EOF
}

command -v tmux >/dev/null || { echo "tmux-xlib.sh: tmux is not installed" >&2; exit 1; }

# The git root of the directory in $1, or empty when it is in no repository.
# -C rather than a cd, so the caller's own cwd never moves.
git_root() {
	git -C "$1" rev-parse --show-toplevel 2>/dev/null
}

# Shell-quote a path for the pane's shell: repo directories hold spaces and
# parentheses (there is a "mms-frontend (copy 1)" on this box).
q() {
	printf '%q' "$1"
}

# One word per path component, lowercased, anything else a separator.
slug() {
	printf '%s' "$1" \
		| tr '[:upper:]' '[:lower:]' \
		| sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

# /storage/GitHub/<group>/<repo> names the session <group>-<repo>; a repo
# outside that tree has no group, so it slugs its whole path instead. The
# group is what keeps two repos sharing a basename — mms-frontend and
# mms-frontend (copy 1) — off one session name, where a bare launch would
# silently kill the other's panel. A worktree has its own path and so its own
# session name, which is what keeps two agents' worktrees off one panel.
session_name() {
	local path="$1" rest name
	case "$path" in
		*/GitHub/*) rest="${path#*/GitHub/}" ;;
		*)          rest="${path#/}" ;;
	esac
	name="$(slug "$rest")"
	printf '%s' "${name:-xlib}"
}

ARG="${1:-}"
NAME="${2:-}"

case "$ARG" in
	-h|--help) usage; exit 0 ;;
esac

# Target resolution: an explicit path wins, then the git root above the cwd,
# then XLib. Never a bare cwd — a launcher pointed at tools/ means the repo.
TARGET="$XLIB_DIR"
if [ -n "$ARG" ]; then
	if [ -d "$ARG" ]; then
		TARGET="$(git_root "$ARG")"
		[ -z "$TARGET" ] && TARGET="$(cd "$ARG" && pwd)"
	else
		echo "tmux-xlib.sh: '$ARG' is not a directory — using $XLIB_DIR" >&2
	fi
else
	ROOT="$(git_root "$PWD")"
	[ -n "$ROOT" ] && TARGET="$ROOT"
fi

SESSION="${NAME:-$(session_name "$TARGET")}"

XLINT="$XLIB_DIR/tools/xlint/xlint.py"
TASKVIEW="$XLIB_DIR/tools/taskview/taskview.py"
SKYNET="$XLIB_DIR/tools/skynet.py"

# Killing the session is deliberate, on the way in and on the way out (human,
# 2026-10-02): the panel takes everything it started down with it, because
# nothing should be left running in the background. Do not "fix" this. To look
# at something outside a panel, use prefix-s inside tmux rather than detaching.

tmux kill-session -t "$SESSION" 2>/dev/null
tmux new-session -d -s "$SESSION" -c "$TARGET"

# Each pane is addressed by the id tmux hands back, never by "the active pane":
# a split that does not take focus leaves the active pane where it was, and an
# id that reads as active after a later split belongs to a different pane.

PANE_XLINT=$(tmux list-panes -t "$SESSION:0.0" -F '#{pane_id}')
tmux send-keys -t "$PANE_XLINT" "python3 $(q "$XLINT") --watch ." Enter

PANE_TASKVIEW=$(tmux split-window -d -P -F '#{pane_id}' -c "$TARGET" -t "$SESSION:0.0")
tmux send-keys -t "$PANE_TASKVIEW" "python3 $(q "$TASKVIEW") --watch" Enter

# skynet reads ~/.local/share/opencode/opencode.db and has no cwd to care
# about; it rides along in the target repo so every pane looks the same.
PANE_SKYNET=$(tmux split-window -d -P -F '#{pane_id}' -c "$TARGET" -t "$SESSION:0.0")
tmux send-keys -t "$PANE_SKYNET" "python3 $(q "$SKYNET") --watch" Enter

# marduk belongs to XLib: agent-coord.py resolves ROOT/.agents, and the module
# is imported as marduk.marduk with tools/ on PYTHONPATH.
PANE_MARDUK=$(tmux split-window -d -P -F '#{pane_id}' -c "$XLIB_DIR" -t "$SESSION:0.0")
tmux send-keys -t "$PANE_MARDUK" "PYTHONPATH=tools python3 -m marduk.marduk --watch" Enter

tmux set-option -g mouse on
tmux select-layout -t "$SESSION:0" tiled

# Leave taskview focused rather than a shell.
tmux select-pane -t "$PANE_TASKVIEW"
tmux select-window -t "$SESSION:0"

echo "tmux-xlib.sh: $SESSION → $TARGET"

tmux attach-session -t "$SESSION"

tmux kill-session -t "$SESSION"
