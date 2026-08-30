#!/bin/bash

#Run it from this folder.
#Then you'll be able to do 'from xlib import blah' or 'from xlib_legacy import blah'
#Note that the change won't take effect until you log in the next time.
#If that's an issue, do this to bypass the problem for one terminal:
#source ~/.profile

echo '# Python global libraries' >> ~/.profile
echo "export PYTHONPATH=\$PYTHONPATH:$PWD" >> ~/.profile