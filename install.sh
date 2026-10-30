#!/bin/bash

#Run it from this folder.
#Then you'll be able to do 'from xlib import blah' or 'from xlib_legacy import blah'
#Note that the change won't take effect until you log in the next time.
#If that's an issue, do this to bypass the problem for one terminal:
#source ~/.profile

# Append the PYTHONPATH export only once, so re-running install.sh does not
# accumulate duplicate lines in ~/.profile.
if ! grep -qF "$PWD" ~/.profile 2>/dev/null; then
	echo '# Python global libraries' >> ~/.profile
	echo "export PYTHONPATH=\$PYTHONPATH:$PWD" >> ~/.profile
fi

# Make the standard panel and agent tools available on PATH by name, the same
# way oc-agent already is: a symlink in ~/.local/bin pointing at the copy in
# this repository. Re-running this script just refreshes the links.
mkdir -p "$HOME/.local/bin"
chmod +x "$PWD/tools/oc-agent" "$PWD/tools/ctx" "$PWD/tools/xlint/xlint.py" \
	"$PWD/tools/taskview/taskview.py" "$PWD/tools/taskview/taskupdate.py" \
	"$PWD/tools/marduk/marduk" "$PWD/tools/skynet.py" \
	"$PWD/tools/bbprs/bbprs.py" "$PWD/tools/tmux-xlib.sh" \
	"$PWD/tools/ruffwatch.py" 2>/dev/null || true
ln -sf "$PWD/tools/oc-agent" "$HOME/.local/bin/oc-agent"
ln -sf "$PWD/tools/ctx" "$HOME/.local/bin/ctx"
ln -sf "$PWD/tools/xlint/xlint.py" "$HOME/.local/bin/xlint"
ln -sf "$PWD/tools/taskview/taskview.py" "$HOME/.local/bin/taskview"
ln -sf "$PWD/tools/taskview/taskupdate.py" "$HOME/.local/bin/taskupdate"
ln -sf "$PWD/tools/marduk/marduk" "$HOME/.local/bin/marduk"
ln -sf "$PWD/tools/skynet.py" "$HOME/.local/bin/skynet"
ln -sf "$PWD/tools/bbprs/bbprs.py" "$HOME/.local/bin/bbprs"
ln -sf "$PWD/tools/tmux-xlib.sh" "$HOME/.local/bin/tmux-xlib"
ln -sf "$PWD/tools/ruffwatch.py" "$HOME/.local/bin/ruffwatch"
echo "Linked panel tools into $HOME/.local/bin"