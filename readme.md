**Where am I?**  
This is the repository for shared libraries in the mallesne project.  
Our main project is Traveller, but there are also numerous smaller projects that will eventually find their way into the Playground repository.  
The shared libraries from this repo are in the xlib folder.  
Run install.sh to make them available, then in python do 'from xlib import blah' to import whichever one.  

**Versioning**  
Shared libraries should be versioned. Example:  
*net5_27_105.py  
*5 is major version. Every breaking version, remove deprecated stuff.  
*27 is minor version. It should not break previous stuff.  
*105 is a revision. Use those for bugfixes and the like. Just fix bugs, don't add stuff or change API.  

**Development**  
It might be necessary for indev versions to have their own folders. That way a central packager script could be used to build new versions for the xlib folder.  
By default the script should probably make revisions.  
Add -minor to change minor version.  
Add -major to change major version.  
Don't do both at once.  
Maybe the packager should be written in python, since it's easier to work with.  

**Maintenance**  
How to know if something is using old code?  
Probably make a library that keeps track of projects and appends their paths to a list if they're in this this repo. If you import this library, the folder your project is running from gets added, unless its parent folder is already included.  
Could then just run a script on the list to go through all their files and look for the filenames in xlib, just without the .py  
That way it would be possible to definitively know whether deprecated code can be removed.  

**Not done**  
Versioning script - as described above.  
Bundling script - it's convenient to develop libraries as multiple files, but use as one.  
Export script - same as bundler, but also folds in any xlib libraries used, for use outside the walled garden.  

**Legacy**  
Due to the large number of legacy projects, it's not reasonable to migrate them all at once.  
At first, it's enough to put all the loose ones into playground and their libraries(if any) into xlib_legacy.  
Keep projects runnable if they were runnable before migration.  
Over time the development of all libraries can be moved into this project and versioned copies can be made. Once there's no legacy libraries left, just delete the xlib_legacy folder. Note that git won't remove folders automatically, since it doesn't track folders, only files.  

**Other projects**
A version of XLib for C or JS.
For JS, the distribution mechanism is a question. lib.mallesne.ee?
