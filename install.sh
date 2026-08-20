#!/bin/bash

#Run it from this folder.
#Then you'll be able to do 'from xlib import blah' or 'from xlib_legacy import blah'
#Note that already opened terminals won't be using it.
#Restart them if that's an issue, or do:
#source ~/.bashrc

echo '# Python global libraries' >> ~/.bashrc
echo "export PYTHONPATH=\$PYTHONPATH:$PWD" >> ~/.bashrc