# Pybundle Spec

**Pybundle** combines python code defined *within a folder* into a single file.
It doesn't inline any any files that are outside the root folder.

It works by:
1. **Inlining** each import at its first occurrence.
2. **Prefixing** all imported names within the imported file.
3. **Rewriting** imported names with the prefixed versions.

## Rationale

This spec is for rewriting pybundle into a single-pass bundler.
The previous version became impossible for agents to handle due to complexity.
The current document is meant to replace it with a simpler design.

## Key constraints

1. Every file is processed only once and immediately inlined.
2. The combined file preserves original behaviour when possible.
3. Code changes are limited to imported names. Local names are not rewritten.
4. Each inlined file leaves behind a comment with where it came from.

## Output format
A single file that contains all inlined files.
The file ordering is identical to the order python would run them.

Each inlined file additionally gets a comment that outlines where it's from.
Example comment:
	"## from foo import bar"

There can be multiple imports per line.
In that case the comments are separate for each file.
Each comment is before the inlined file it refers to.

For example, if the import line was:
	from foo import bar,baz
The resulting comments would be:
	"## from foo import bar"
	"## from foo import baz"

## Name translation

Names are translated by taking the full modpath of the file,
then replacing each . in the modpath with __

Every module name is treated as if it were the full modpath instead.
For example, when the root is at:
	/server.py
A module at:
	/py/command/api.py
Imported from /py/command/map.py as:
	from . import api
Will be handled as if it were imported with:
	import py.command.api

Then, when rewriting a reference to it, it will turn:
	api.run()
Into:
	py__command__api__run()

## Control flow

**main**() -> int_result
Processes commandline parameters to decide what to do.
The arguments are:
	--in	root file path
	--out	bundled result path
Explanation:
	Gives an error when either of the parameters is missing,
	or when there are extra parameters provided.
	Otherwise calls *file.process*
	Returns 0 on a success, 1 on any error.
	Providing the wrong parameters prints usage instructions.
Example usage:
	python3 pybundle.py --in /path/to/root.py --out /path/to/bundle.py

**file.process**(fpath_in,fpath_out) -> int_result
Sets up the shared state used for the process.
Calls *file.inline* on the root file.

**file.inline**(modpath,file_out,modules) -> None
	*modpath* is the path of the imported file.
	*file_out** is the handle of the output file being written to.
	*modules* is a list of all currently inlined modpaths.
First adds the modpath of the current file to modules.
Then finds and handles all import lines in order. For each import line:
	*import.resolve* to find out modpaths
	*file.inline* to process them.
Then goes line by line and translates names. Is aware of function scope.
Inlines imports and keeps track of what has been inlined in the current file.
Rewrites global and imported names.

**import.resolve**(line_import,modpath_source,modules) -> modpath[],import_line
Takes an import line and the module path of the file it was in.
If the import line contains " as ", throw the *IMPORT_AS* error.
If an import is already in modules, drop it and print an informative message.
Returns 2 values:
	modpaths - A list of module paths resolved relative to root. (this is *not* modules)
	import_line - the remaining import line without the resolved modules, or None

## Shared state

list **modules** - Python module paths that have already been resolved.
str **root** - Full path of the initial file.

## Edge cases

**Relative imports**
Handled in import.resolve.
The current file's module path is provided.
Replace the last part of the module path with the file's name.
Follow the ordinary python rules - root file is not allowed to have them.

**__init__.py**
Match python behaviour.
Trying to import a folder actually imports that folder's __init__.py
If the import is:
	from example.path.here import blah
The prefix would be:
	example__path__here____init____blah

**Circular imports**
Each file is inlined immediately.
Further imports of the same file are dropped.
Code that depends on circular imports is allowed to break.
Detecting whether a circular import would cause real issues is out of scope.
Therefore there will be no errors for them.

**Conditional imports**
All imports are handled as if they were at the top of the file.
When an import is indented, a pass statement will remain where it was.
Indented imports will not be analyzed to figure out why they're indented.
This will import blah:
	if False: import blah
Any complex behaviour depending on it will not be supported.
You can use importlib to bypass this issue if needed.

**Dynamic imports**
For example: __import__ and importlib
Will not be supported.

**Name collisions**
Assumed to not happen.
Will not be detected or fixed when they do.

**Errors in source**
The only relevant errors are those that affect the bundler itself.
Will not be supported otherwise.

## Errors

Will pass on ordinary errors like "file not found" or permission errors.
**They will not be listed here.**

This section describes errors specific to pybundle.

**IMPORT_FILE_NOT_FOUND**
When a file isn't found and it's definitely not a global.
For example, from a relative import.
Suspected globals don't throw an error.

**RELATIVE_IMPORT_IN_ROOT**
Python doesn't allow those.
If the bundler encounters them, it should throw an error.

**IMPORT_AS**
Will exist for as long as "import as" is not supported.
Resolver throws this errors when it encounters " as ".

## Future development

**Import as**
Not supported initially.
Code that uses "import as" will throw *IMPORT_AS*

**Name imports**
Python allows importing modules, but also names from within modules.
For example, you can import a specific function or variable.
Initially not supported. Support can be added later if needed.
For now, any code with name imports will fail with: "import file not found"

**from xlib import blah**
Will be supported as an option eventually.
When it is, XLib imports will be possible to inline.
Perhaps this will be a generic "also treat that folder as root" logic.

**Anything we won't support**
Things that weren't supported initially can be supported later.
Tracking down bugs is hard and pybundle should help when possible.
However, pybundle should first of all be a tool for bundling.
Trying to catch every single issue is not practical at first.

## Test cases

TODO

## Terms

**root path**(root)
The file path that is first passed to the program.

**root folder**
The parent folder of the root path.

**module path**(modpath)
Project-local path that python uses to identify modules.
For a file with the path /example/path/here.py it becomes:
	example.path.here
For a file with the path /example/path/__init__.py it is:
	example.path

## NOTES

Make AI produce a call graph when making other specs. For each stage, talk what happens and what errors can come up.
