#!/bin/bash

SESSION="${1:-xlib}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XLIB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

tmux kill-session -t "$SESSION"

tmux new-session -d -s "$SESSION"
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 xlint/xlint.py --watch ." Enter

tmux split-window -h
tmux send-keys -t "$SESSION" "cd $XLIB_DIR" Enter

tmux split-window -h
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 tools/skynet.py --watch" Enter

tmux set-option -g mouse on
tmux select-layout tiled

tmux select-window -t "$SESSION:0"
tmux attach-session -t "$SESSION"

tmux kill-session -t "$SESSION"
