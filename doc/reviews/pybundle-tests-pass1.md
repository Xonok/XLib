# pybundle — pass 1: test derivation and spec validation

**2026-10-15.** Reviewer pass 1 on `tools/pybundle/SPEC.md`, derived against
`tools/pybundle/DRAFT.md`. 65 tests in three files, and twelve spec flaws — the
flaws are the deliverable, and six of them are blocking.

The tests compile and pass xlint. They do not run: there is no implementation,
which is the state the stage is supposed to be in.

## What was derived, and how

The seam is `main(entry_path, out)` — the one entry point whose arguments and
return the spec fixes outright (D5's call graph, R5 for the sink). Every test in
`test_bundler.py` writes a throwaway source tree into a temp folder, calls
`main`, and asserts on the bundle. That choice is deliberate: the shapes the
three leaf functions hand back are **not** settled by the spec (F1–F3), and
writing unit tests against them would have meant inventing them.

Two things are therefore tested directly instead:

- `renamed(name, prefix)`, which D4 names as "the one most worth testing on its
	own" and whose signature and return are fully specified — 11 tests in
	`test_bundler_names.py`.
- The structure requirements in R6 and D4, by reading the sources — 3 tests in
	`test_bundler_structure.py`. The spec's goal section says structure is a
	requirement "here, not an implementation preference", so forbidding `ast` by
	name and naming the file each function lives in are contracts like any other.

The pipe test is a real `os.pipe()` write end, not a stand-in. `YEBP3QB` asked for
that specifically, and it is the test that fails if the core takes a path and
pretends to be file-like.

## Traceability

Every requirement in the spec, and what tests it.

| Spec | Tests |
|---|---|
| R1.1 root folder is the entry's parent | `TestInliningR1` throughout — every fixture's root folder is the entry's parent |
| R1.2 local iff in the root folder or below | `test_module_in_the_root_folder_is_inlined`, `test_module_in_a_subfolder_is_inlined`, `test_file_outside_the_root_folder_is_not_inlined`, `test_file_outside_the_root_folder_is_left_as_a_normal_import`, `test_a_local_file_shadows_a_standard_library_name` |
| R1.3 every import checked, local ones inlined | `test_indented_local_import_is_inlined_even_under_a_false_condition`, `test_a_local_file_shadows_a_standard_library_name` |
| R1.4 imports placed before the file's own code | `test_imported_code_is_written_before_the_importing_file`, and every `_start_comments` assertion, which pins order |
| R1.5 non-local imports stay where they were | `test_non_local_import_stays_between_its_own_neighbours`, `test_indented_non_local_import_stays_indented` |
| R1.6 second reference dropped | `test_second_reference_to_a_module_is_dropped`, `test_a_dropped_import_leaves_nothing_behind` |
| R1.7 root seeded into the handled set | `test_module_importing_the_root_emits_the_root_once_and_last` |
| R2 ordering and the comment pair | `test_a_file_one_folder_down_carries_a_leading_slash`, `test_end_comment_is_the_start_comment_with_a_bang`, `test_the_root_file_gets_the_same_comment_pair_as_everything_else` |
| R2 `##` / `##!`, root not special | same three |
| R3 prefix is the flattened path below the root | `test_global_name_gets_the_file_prefix`, `test_nested_path_prefix_is_flattened_with_double_underscore`, `test_module_global_is_prefixed_with_the_file_prefix`, `test_init_file_globals_are_prefixed_with_its_own_component` |
| R3 module names treated as full modpaths | `test_a_relative_import_reference_uses_the_full_modpath_prefix`, `test_a_reference_through_a_module_name_becomes_the_prefixed_global`, `test_an_aliased_import_reaches_the_same_renamed_global` |
| R3 leading underscores move in front | `TestLeadingUnderscores` (5), `test_private_global_keeps_its_underscores_in_front_of_the_prefix` |
| R3 the root's own names are exempt, and only those | `test_root_own_definitions_are_not_translated`, `test_a_sibling_in_the_root_folder_is_translated_even_beside_the_root` |
| R4 scope-aware, function and class | `TestScopeR4` (14) |
| R4 `global` renames and does not block | `test_global_name_is_translated_with_the_file_prefix`, `test_global_statement_names_are_translated_too` |
| R4 `nonlocal` does neither | `test_nonlocal_name_is_neither_translated_nor_blocked` |
| R5 anything file-like, one code path | `test_a_file_sink_produces_the_same_bytes_as_a_buffer`, `test_a_real_pipe_produces_the_same_bytes_as_a_buffer` |
| R5 never closes a sink it did not open | `test_a_buffer_the_bundler_was_given_is_not_closed`, `test_a_file_the_bundler_was_given_is_not_closed` |
| R6.1 no parse tree | `test_no_module_of_the_bundler_imports_ast` |
| R6.2 state piped, never global | `test_a_run_after_another_matches_the_same_run_alone` |
| R6.3 nothing imports the entry file | `test_only_the_entry_module_imports_the_other_modules` |
| D1 statements, not lines | `test_dict_continuation_lines_do_not_bind_names_in_the_function`, `test_a_multiline_string_containing_a_def_does_not_open_a_block`, and every `TestScopeR4` binding form, which is only correct if continuation lines are not scanned |
| D2 blocks by indentation, nested blocks stack | `test_nested_function_inherits_the_outer_block` |
| D2 binding forms | `test_function_local_assignment_blocks_the_rename`, `test_function_parameter_blocks_the_rename`, `test_augmented_assignment_blocks_the_rename`, `test_annotated_assignment_blocks_the_rename`, `test_for_target_blocks_the_rename`, `test_with_as_target_blocks_the_rename`, `test_except_as_target_blocks_the_rename`, `test_walrus_target_blocks_the_rename`, `test_class_body_name_blocks_the_rename` — **function-local `import` has no test, see F10** |
| D3 the root exception is the empty prefix | `TestRootIsTheEmptyPrefix` (2) |
| D4 the function set and its file per function | `test_each_function_of_the_set_lives_in_the_file_the_table_names` |
| D5 call graph — `main` and `inline` | every test in `test_bundler.py`, which drives `main` |
| D6 `__init__.py` is an ordinary component | `test_init_file_contributes_its_own_name_as_a_path_component`, `test_init_file_globals_are_prefixed_with_its_own_component` |
| D6 `import x as y` reaches the same place | `test_an_aliased_import_reaches_the_same_renamed_global` |
| D7 staged vs excluded | `test_a_name_import_raises` (name imports are not supported initially) |
| IMPORT_FILE_NOT_FOUND | `test_relative_import_of_a_missing_module_raises` |
| NOT_A_MODULE | `test_a_name_import_raises` |
| RELATIVE_IMPORT_IN_ROOT | **no test — F6** |
| Command line: flags, usage, exit codes | **no test — F7** |
| R1.6 "an informative message" | **no test — F9** |
| Edge case: name collisions | not tested, and deliberately so: D7 excludes collision handling and no requirement states an outcome |
| Edge case: dynamic imports, circular-import analysis | not tested; circular imports are covered by R1.6 instead |

The other direction: every test maps to a row above. The exceptions are named in
*Blocked and not written* below, and none of them is a test that exists without a
requirement behind it.

## Spec flaws

Ordered by what they block. All of these are places where deriving a test
required a decision the spec does not contain, which per `doc/development.md` is
a flaw for the human to fix rather than an assumption for me to make.

### F5 — `inline` cannot be called as written (blocking)

D4 gives `inline(modpath, out, seen, entry)` (line 191). D5's body for it reads
`statements(read(modpath))` and calls `imports(stmts, modpath, root)` (lines
212–214). So `inline` needs the root folder — to read files, and to pass down —
and its signature does not carry it. Where `root` comes from inside `inline` is
unstated, and R6.2 rules out module-level state.

This is why the suite calls `main` and never `inline`. It also means the spec's
one and only call graph cannot be executed as written.

Options: add `root` to the signature (`inline(modpath, root, out, seen, entry)`);
or pipe a modpath that is already a path; or drop the file reading from `inline`
and give it text.

### F7 — the command line has no home (blocking, and larger than it looks)

Three separate problems in one place.

1. **`main` names two different functions.** D4 and D5: `main(entry, out)` takes
	a sink and calls `inline`. *Command line* (line 305): "`main` does the
	transformations the core does not: `--out -` or an absent output becomes
	`sys.stdout`, and a path becomes an opened file." If it is one function, `out`
	is either a file-like or a path, and D5's `out.write(...)` inside `inline`
	requires a file-like. If it is two, the second one is not in the set.
2. **Nothing parses argv, prints usage, or returns an exit code.** The draft's
	superseded `main() -> int_result` did all three (DRAFT line 193), and
	*Superseded draft text* replaces it with D4's table (SPEC.md line 318) without
	naming a successor. Exit code 0/1 and "usage is printed" (line 303) have no
	function to live in.
3. **`--out` is both required and allowed to be absent.** Line 302 says both
	flags are required; line 305 handles an absent output. If the absent case is
	a library-level `main(entry, None)`, say so — otherwise one of the two lines
	is unreachable and the tests cannot tell which.

Until this is settled the entire command-line surface is untestable, which also
means the `--out -` path through `sys.stdout` has no test.

### F4 — nobody removes the statements of inlined imports (blocking, partial)

R1.4 requires a file's imports to be handled before its own code is written, and
the edge cases require a `pass` where an indented import was (line 266). But D5
writes the file's block as `out.write(translate(stmts, renames))` — the same
statement list, whole. Nothing in the set is assigned the job of deleting
`import helper` once `helper` has been inlined.

If `translate` does it, then the rule needs writing down, and `renames` has to be
what marks an import as inlined — which is a responsibility the D4 table does not
give `translate` ("with its names moved"). If `inline` does it, `translate`'s
signature changes or a third hand-off appears, which D4 says it does not.

A second, smaller gap in the same place: **`import helper, os`** — one local
target and one non-local on the same line. The local half is inlined; the spec
never says what the line becomes. The old draft's `import.resolve` returned "the
remaining import line without the resolved modules"; the rewrite dropped that
return value and never replaced it.

### F1, F2, F3 — the three leaves' return shapes (blocking for direct tests only)

The draft's own list of things to settle included "data formats, as far as they
affect the result of the bundler's actual running" (DRAFT line 372). These
formats affect it, and they are not written down:

- **`statements(text)`** — a statement must carry its text and its indentation,
	because D1 and D2 both depend on the latter. The container is not specified,
	and D4 says this value is handed to two other modules, so the shape is a
	cross-module contract. Line numbers are *not* required by anything in the spec,
	and the earlier draft of these tests asserted one anyway.
- **`translate(statements, renames)`** — D5 line 221 has `out.write(translate(...))`,
	and `write` takes text. Nothing says so, and nothing says how statements are
	joined or whether the result carries a trailing newline.
- **`imports(statements, modpath, root)`** — D6 says it resolves "to zero or
	more local targets, each with a modpath and the name it binds, **or** to a
	non-local result that is left in place". The "or" leaves two return shapes
	(a list of pairs, or a list of objects with attributes) and leaves it open
	whether a non-local statement yields an entry or nothing.

I did not paper over these: the suite goes through `main`, so no test depends on
a shape the spec has not fixed. If you would rather have the leaves tested
directly, settle these three and the direct tests follow.

### F6 — RELATIVE_IMPORT_IN_ROOT cannot be raised (blocking, one error)

D6 says "The root file may not use them" and the Errors section lists
RELATIVE_IMPORT_IN_ROOT for it. But `imports(statements, modpath, root)` receives
the root **folder**, never the entry, and D3 is explicit that the root exception
is per file identity and not per location — a sibling in the root folder is
translated, so "is this the root?" cannot be answered from the path. No function
in the set learns which file is the entry except `inline`, and `inline` is
handed `entry` — so the check has a plausible home there, or in an `entry`
parameter added to `imports`, or nowhere.

This is the one error in the Errors section with no function that can raise it.

### F8 — star imports have no stated behaviour (blocking, one test)

D7 stages `from x import *` with name imports. NOT_A_MODULE is defined as "an
import of a specific name" — `*` is not a specific name. So three behaviours are
available (NOT_A_MODULE, left in place, IMPORT_FILE_NOT_FOUND) and the spec
picks none. A test cannot be written that is more than a guess.

### F12 — R3's last sentence and D7 do not agree about name imports (blocking, one test)

R3 line 96: "Names the root imports *are* translated — only the root's own
definitions are exempt." Under D7 and the Errors section, the only way to import
a *name* is `from x import name`, which raises NOT_A_MODULE. The sentence
therefore only means something if "names the root imports" means the module names
bound by `import`.

Q19's example — "a root doing `from helper import count` gets `helper__count`" —
is itself a name import, so it describes later-stage behaviour, exactly as Q6
says of the draft's other name-import example.

The suite tests `from helper import count` as **raising** NOT_A_MODULE, because
that is what D7 and the Errors section say. If you meant the Q19 reading instead,
that one test is wrong and D7 has to change, not the test.

### F9 — where the dropped-import message goes

R1.6 says a second reference is "dropped with an informative message" and does
not say where the message goes. It matters: if it goes to stdout it corrupts the
bundle whenever the sink *is* stdout, which R5's byte-for-byte identity then
forbids. So the message must not reach the sink — that much is derivable and is
what `test_a_dropped_import_leaves_nothing_behind` checks — but the sink for the
message itself is unspecified.

### F10 — a bare module reference, and the one binding form it blocks

The worked example covers `api.run()`. Nothing covers `api` on its own, and in a
bundle the module object is in the bundle under no name at all, so there is no
obvious rewrite. This is why D2's **function-local `import`** has no test: the
binding it establishes is over a bare module name, so the test would be asserting
behaviour the spec does not have. Every other D2 binding form is covered.

### F11 — the draft's *Key constraints* never became requirements

DRAFT lines 30–35 list four constraints. None of them is a numbered requirement
in `SPEC.md`. Constraint 3 — "Code changes are limited to imported names. Local
names are not rewritten" — is the one that says text which is not a name
survives into the bundle unchanged: comments, blank lines, spacing.

The suite mostly avoids depending on it, by asserting on the renamed form rather
than on the surroundings around it. But `test_dict_continuation_lines_do_not_bind_names_in_the_function`
and the `TestScopeR4` block in general do rely on unchanged non-name text to be
meaningful. Folding the four constraints in as requirements costs a paragraph and
removes the reliance.

## Blocked and not written

| Requirement | Blocked by | What is missing |
|---|---|---|
| Command line: `--in`, `--out`, usage, exit 0/1, `--out -` | F7 | which function parses argv, and whether `main` takes a sink or a path |
| RELATIVE_IMPORT_IN_ROOT | F6 | a function that learns which file is the entry |
| star imports | F8 | any stated behaviour |
| R1.6's informative message | F9 | the sink the message goes to |
| D2's function-local `import` | F10 | what a bare module reference becomes |
| direct tests of `statements`, `imports`, `translate` | F1–F3 | their return shapes |
| direct tests of `inline` | F5 | a signature it can be called with |

Every error, every requirement and every decision in the spec is either covered
above or listed here. Nothing is untested and unaccounted for.

## What changed from the tests that were already in the folder

`tools/pybundle/test/` held three untracked files from an earlier session. Two
were removed and one rewritten, because they encoded assumptions the spec does
not support, and in four cases assumptions it contradicts. Listing them here
because each one is a place a reader could otherwise think the spec says
something it does not.

- **`from x import y` treated as a module import.** `test_from_import_module_local`
	asserted that `from helper import client` resolves to `helper.client`. D7 and
	the Errors section make it a later-stage feature that raises NOT_A_MODULE.
	Five tests rested on this.
- **`imports` called with no files on disk.** The tests passed `root="/project"`
	with nothing there, and then asserted `import helper` was local and `import os`
	was not. The two are textually identical; only the filesystem tells them apart,
	and R1.2 makes locality a question about location. Every test in this suite
	writes a real tree.
- **`def foo():` not renamed.** `test_function_name_not_translated_in_its_own_def`
	asserted the `def` line survives unchanged while
	`test_function_name_translated_when_called` asserted `foo()` becomes
	`helper__foo()`. Together those produce a bundle that does not work: the
	definition and its only call site end up with different names. D5 renames a
	file's own globals, and a function name is one.
- **`global` at module level treated as reaching into a function.** One test had
	`global foo` at module level and asserted an assignment to `foo` inside a
	function was still translated. In python that assignment makes `foo` local to
	the function, and R4 says a local binding blocks. The test now puts `global`
	where the spec means it.
- **`relative_import_parent` and `import_file_not_found_relative` disagreed.**
	One asserted `from .. import x` from a three-part modpath resolves without
	error, the other asserted the same shape raises, with nothing in the fixtures to
	tell them apart. Both are now driven by real files.

Two things from those files were kept: the `__init__.py` handling and the relative
import level arithmetic, both of which the spec does support and which now run
against a tree that exists.

## What the human has to do

1. Append decisions to `SPEC.md` for F5, F7, F4, F1–F3, F6, F8 and F12, per the
	process on epiq `6MFX0Z1` step 3. The rest can be settled later or not at
	all; nothing else is blocked on them.
2. Sign off on the tests, or tell me which derivation to redo. The suite is
	written against the current spec, so any of these decisions that changes
	behaviour will change tests with it.
3. Nothing here touches the implementation, which does not exist.

## One reading I had to pick, flagged rather than buried

D5's call graph is the only place that says what `main` takes, and it takes a
file-like sink. The *Command line* section reads as though it also opens files.
The suite calls `main(entry_path, file_like)` — the D5 reading — because D5 is
the concrete statement and R5 says the core never opens or closes. If the split
goes the other way, `main` keeps this signature and a separate function owns argv;
no test in this suite changes.
