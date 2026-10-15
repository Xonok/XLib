# pybundle — pass 1, second derivation

**2026-10-15.** Re-derived against `tools/pybundle/SPEC.md`, after the *Decisions
— test pass 1* section (D8–D19) and after the human answered F13–F17 in
session. 138 tests in five files, and three open spec flaws.

The tests compile and pass xlint. They do not run: there is no implementation,
which is the state this stage is supposed to be in.

Supersedes the counts in `pybundle-tests-pass1.md`, which described the suite
before the decisions. That file stays as the record of the first derivation.

## What the human's answers changed

Five of the nine flaws from the first re-derivation are answered. Two of them
changed tests rather than unblocking them, which is the interesting part: **the
answer to F13 removed a mechanism the spec had already committed to in two other
decisions.**

| Flaw | Ruling | Effect |
|---|---|---|
| F13 | `from x import y` needs no rebinding. `y` a file means `import x.y`; `y` a name in `x` means every use of `y` is treated as `x.y`. Either way it lands at `x__y`, prefixed by where `x` lives. | Five tests rewritten, one deleted. D9 and D19 now describe a mechanism that no longer exists — see F23 |
| F14 | The program name does not matter to the person running it. Only to `cli`'s signature. | Proceeding with arguments-only; one clause settles it |
| F15 | A missing input file is a cli error | Two tests added |
| F16 | `statements` returns dictionaries; propose the field names | Two names proposed, both mine, both documented below |
| F17 | Empty lines and comments pass through. Rules about statements are about not breaking a dict definition, not about removing "unnecessary" parts. | Two tests kept as they were; D1 needs a clause |

## Tests the answers invalidated

Five rewritten, one deleted, one more changed what it is evidence for.

| Test | What happened |
|---|---|
| `test_a_root_name_import_becomes_a_rebinding_to_the_prefixed_global` | **Deleted.** Asserted `count = helper__count`, a rebinding. There are none. Replaced by `test_a_root_name_import_rewrites_the_use`, which asserts the *use* is rewritten. |
| `test_a_name_imported_into_the_root_keeps_its_own_name_where_it_is_used` | **Rewritten.** Asserted `value = count` survived. It does not: it becomes `value = helper__count`. This was the test I wrote because D10 said an imported name is the root's own global. Under the new rule it is not a binding at all — it is a use, and uses get rewritten. |
| `test_a_non_local_name_import_is_aliased_to_the_importing_files_prefix` | **Rewritten.** Asserted `from pathlib import join as sub__client__join`. Now the statement becomes `import pathlib`, because `join` is used as `pathlib.join` and that is the statement that binds `pathlib`. |
| `test_a_use_of_a_non_local_name_import_follows_the_alias` | **Rewritten.** `value = sub__client__join` becomes `value = pathlib.join` — no prefix, because pathlib is outside the root folder. |
| `test_a_star_import_of_a_local_module_rebinds_every_global_it_defines` | **Deleted.** A rebinding again. No replacement yet: what a star import's *uses* become is F22, and I am not inventing it. |
| `test_a_root_name_import_rebinding_is_unprefixed` | **Deleted.** Existed only to pin D19's fourth bullet, which was about a rebinding that no longer exists. Replaced by `test_a_name_import_from_a_non_local_module_binds_an_unprefixed_name`, which pins the case D19's *exception* paragraph now describes. |
| `test_indented_local_import_leaves_a_pass_where_it_was` | **Changed** (earlier in this pass, not by your answer). Uses the plainly indented form, because D8's "removed entirely" and the Edge cases' `pass` rule disagree about the one-line compound body. F18. |

## Traceability

Every requirement in the spec, and what tests it.

| Spec | Tests |
|---|---|
| R1.1 root folder is the entry's parent | `TestInliningR1` throughout — every fixture's root folder is the entry's parent |
| R1.2 local iff in the root folder or below | `test_module_in_the_root_folder_is_inlined`, `test_module_in_a_subfolder_is_inlined`, `test_file_outside_the_root_folder_is_not_inlined`, `test_file_outside_the_root_folder_is_left_as_a_normal_import`, `test_a_local_file_shadows_a_standard_library_name` |
| R1.3 every import checked, local ones inlined | `test_indented_local_import_is_inlined_even_under_a_false_condition`, `test_a_local_file_shadows_a_standard_library_name` |
| R1.4 imports placed before the file's own code | `test_imported_code_is_written_before_the_importing_file`, `test_circular_import_raises_nothing`, and every `_start_comments` equality, which pins order |
| R1.5 non-local imports stay where they were | `test_non_local_import_stays_between_its_own_neighbours`, `test_indented_non_local_import_stays_indented` |
| R1.6 second reference dropped | `test_second_reference_to_a_module_is_dropped`, `test_a_dropped_import_leaves_nothing_behind`, `test_a_dropped_second_reference_writes_a_message_to_stderr` |
| R1.7 root seeded into the handled set | `test_module_importing_the_root_emits_the_root_once_and_last` |
| R2 ordering and the comment pair | `test_a_file_one_folder_down_carries_a_leading_slash`, `test_end_comment_is_the_start_comment_with_a_bang`, `test_the_root_file_gets_the_same_comment_pair_as_everything_else` |
| R2 `##` / `##!`, root not special | same three |
| R3 prefix is the flattened path below the root | `test_module_global_is_prefixed_with_the_file_prefix`, `TestPrefixApplied` (3), `TestNonAsciiNames` (1), `test_init_file_globals_are_prefixed_with_its_own_component` |
| R3 module names treated as full modpaths | `test_a_relative_import_reference_uses_the_full_modpath_prefix`, `test_a_reference_through_a_module_name_becomes_the_prefixed_global`, `test_an_aliased_import_reaches_the_same_renamed_global` |
| R3 leading underscores move in front | `TestLeadingUnderscores` (5), `test_private_global_keeps_its_underscores_in_front_of_the_prefix` |
| R3 root's own names exempt, and only those | `test_root_own_definitions_are_not_translated`, `test_a_sibling_in_the_root_folder_is_translated_even_beside_the_root` |
| R4 scope-aware, function and class | `TestScopeR4` (14) |
| R4 `global` renames and does not block | `test_global_name_is_translated_with_the_file_prefix`, `test_global_statement_names_are_translated_too` |
| R4 `nonlocal` does neither | `test_nonlocal_name_is_neither_translated_nor_blocked` |
| R5 anything file-like, one code path | `test_a_file_sink_produces_the_same_bytes_as_a_buffer`, `test_a_real_pipe_produces_the_same_bytes_as_a_buffer`, `test_the_bundle_cli_writes_is_the_bundle_main_writes` |
| R5 never closes a sink it did not open | `test_a_buffer_the_bundler_was_given_is_not_closed`, `test_a_file_the_bundler_was_given_is_not_closed`, `test_the_out_file_holds_the_whole_bundle` |
| R6.1 no parse tree | `test_no_module_of_the_bundler_imports_ast` |
| R6.2 state piped, never global | `test_a_run_after_another_matches_the_same_run_alone` |
| R6.3 nothing imports the entry file | `test_only_the_entry_module_imports_the_other_modules` |
| R7 only names are rewritten | `TestNonNameTextSurvivesR7` (3), `TestNonCodeLinesAreKeptD18` (3) |
| D1 statements, not lines | `TestStatementBoundariesD1` (8), `TestStatementShapeD16` (7), `TestEmptyInput` (1), `test_dict_continuation_lines_do_not_bind_names_in_the_function`, `test_a_multiline_string_containing_a_def_does_not_open_a_block`, and every `TestScopeR4` binding form, which is only correct if continuation lines are not scanned |
| D2 blocks by indentation, nested blocks stack | `test_nested_function_inherits_the_outer_block` |
| D2 binding forms | `test_function_local_assignment_blocks_the_rename`, `test_function_parameter_blocks_the_rename`, `test_augmented_assignment_blocks_the_rename`, `test_annotated_assignment_blocks_the_rename`, `test_for_target_blocks_the_rename`, `test_with_as_target_blocks_the_rename`, `test_except_as_target_blocks_the_rename`, `test_walrus_target_blocks_the_rename`, `test_class_body_name_blocks_the_rename` — **function-local `import` has no test, see F19** |
| D3 the root exception is the empty prefix | `TestRootIsTheEmptyPrefix` (2) |
| D4/D12 the function set and its file per function | `test_each_function_of_the_set_lives_in_the_file_the_table_names` |
| D5/D12 call graph — `main` and `inline` | every test in `test_bundler.py` drives `main`; `TestInlineD11` (3) drives `inline` |
| D6 `__init__.py` is an ordinary component | `test_init_file_contributes_its_own_name_as_a_path_component`, `test_init_file_globals_are_prefixed_with_its_own_component` |
| D6 `import x as y` reaches the same place | `test_an_aliased_import_reaches_the_same_renamed_global` |
| D6 relative imports resolve; the root may not | `test_a_relative_import_reference_uses_the_full_modpath_prefix`, `test_a_relative_import_in_the_root_file_raises`, `test_a_relative_import_in_a_non_root_file_does_not_raise` |
| D7 staged vs excluded | the staging list is empty as of D9; nothing to test |
| D7 excluded on purpose | not tested, and deliberately so: dynamic imports, circular-import problem detection, and collision detection. `test_a_non_local_name_collision_is_not_warned_about` pins the last of them from the other side — that the declined warning stays declined |
| D8 an inlined import's statement is removed | `test_an_entirely_local_import_statement_is_removed`, `test_a_name_import_statement_is_removed`, `test_a_star_import_of_a_local_module_removes_the_star_statement` |
| D8 a mixed statement keeps the non-local half | `test_a_mixed_import_statement_keeps_the_non_local_half`, `test_a_mixed_import_statement_loses_the_local_half`, `test_a_mixed_statement_keeps_the_remaining_targets_in_source_order` |
| D8 a non-local statement is never removed | `test_a_non_local_import_statement_is_never_removed` |
| D8 one entry per import statement, in source order | observable through the block order every `_start_comments` assertion pins; no direct test, and none needed — see F16 |
| D9 a name imported from a module is not rebound | `test_a_name_imported_from_a_local_module_becomes_the_prefixed_global`, `test_a_name_import_from_a_local_module_emits_no_rebinding`, `test_a_root_name_import_rewrites_the_use` |
| D9 `y` a file means `import x.y` | `test_a_from_import_of_a_module_is_the_module_path`, `test_a_relative_import_reference_uses_the_full_modpath_prefix` |
| D9 a name imported from a non-local module becomes a module import | `test_a_name_import_from_a_non_local_module_becomes_a_module_import`, `test_a_use_of_a_non_local_name_import_becomes_an_attribute_of_it`, `test_a_name_import_from_a_non_local_module_binds_an_unprefixed_name` |
| D9 a star import of a non-local module stays and warns | `test_a_star_import_of_a_non_local_module_is_left_in_place`, `test_a_star_import_of_a_non_local_module_warns` |
| D9 a star import of a local module | `test_a_star_import_of_a_local_module_removes_the_star_statement` only — **what its uses become is F22** |
| D11 `inline` takes the root folder | `TestInlineD11` (3) |
| D13 the command line | `TestSuccess` (3), `TestStdoutSink` (4), `TestUsage` (8), `TestBundlerErrors` (3) |
| D14 diagnostics to stderr, none to the sink | `TestDiagnosticsGoToStderrD14` (3), `test_a_diagnostic_warns_on_stderr_while_stdout_carries_only_the_bundle`, `test_usage_is_printed_on_stderr`, `test_usage_is_not_printed_on_stdout`, `test_a_dropped_second_reference_writes_nothing_to_stdout` |
| D15 the two remaining errors | `test_relative_import_of_a_missing_module_raises`, `test_a_missing_absolute_import_is_left_in_place`, `test_a_relative_import_in_the_root_file_raises`, `test_a_bundler_error_is_reported_on_stderr`, `test_a_relative_import_in_the_root_returns_one` |
| D16 the leaves' return shapes | `TestTranslateD16` (5), `TestStatementShapeD16` (7), `TestStatementBoundariesD1` (8), `TestEmptyInput` (1) |
| D17 bare module references | `test_a_bare_module_reference_is_carried_into_the_bundle_unchanged`, `test_a_bare_module_reference_is_not_detected` |
| D18 / R7 non-name text survives | `TestNonNameTextSurvivesR7` (3), `TestNonCodeLinesAreKeptD18` (3) |
| D19 collisions are between unprefixed names | `TestNameCollisionsD19` (4) |
| Edge case: conditional imports | `test_indented_local_import_is_inlined_even_under_a_false_condition`, `test_indented_local_import_leaves_a_pass_where_it_was`, `test_indented_non_local_import_stays_indented` |
| Edge case: circular imports | `test_circular_import_raises_nothing` |
| Edge case: name collisions | `TestNameCollisionsD19` (4) |
| Edge case: errors in source | not tested — it excludes a class of behaviour rather than stating one |

The other direction: every test maps to a row above. The exceptions are named in
*Blocked and not written*, and none of them is a test that exists without a
requirement behind it.

## The two field names, which are mine

F16 was answered: the entries from `statements` are dictionaries, and I should
propose the names. These are the proposal. **They are not in the spec, and until
they are written in, an implementer is free to choose otherwise and two tests
will fail for a reason that is not a bug.**

| Field | What it holds | Why this spelling |
|---|---|---|
| `text` | the statement's source text, its first line's indentation included, no trailing newline | D16 says "its text", so the name is the spec's own word |
| `indent` | that same leading whitespace, as a string | D16 says "its indentation". A string rather than a column count, because it round-trips exactly and because there is no unit to agree on |

Two notes on choices I had to make inside that. The text of a multi-line
statement carries **every** line, because R7 requires the text to survive
unchanged and joining statements has to be able to put the file back. And
`indent` is the **first** physical line's whitespace, which D1 already states.

The alternative for `indent` is a column count, in which case a tab is eight
columns because that is what the tokenizer computes. I chose the string because
D2's comparison can use the tokenizer's own INDENT and DEDENT tokens without
either form having to be re-derived. If you prefer the count, it is a one-line
change to three tests.

Nothing is proposed for `imports`' entries. D8's "in source order" is already
pinned behaviourally — if the entries came back out of order the inlined blocks
would come out in the wrong order, which several `_start_comments` assertions
would catch — so no test needs a field name, and I am not inventing four.

## Spec flaws

Three remain. None of them blocks the suite as it stands; F22 and F24 leave
three tests unwritten.

### F22 — a star import of a local module has no mechanism left

D9 gave `from helper import *` its rebindings: "emits one rebinding per global
of `helper`". The F13 ruling removed rebindings for `from x import y`, and a star
import cannot use the mechanism that replaced them either — it names nothing, so
there is no use to rewrite into `helper__x`.

What is left is to put every defined global of the inlined module into the
importing file's rename table, so that each use of `count` in that file is
rewritten to `helper__count` as it is read. That reaches the same bundle as D9's
rebindings without emitting a statement, and it is consistent with the F13
ruling rather than against it. But the spec does not say it, and I am not going
to pick between "one rebinding per global" and "every global into the rename
table" on my own — they differ in whether a file that also defines `count`
itself gets a conflict.

What is tested: `test_a_star_import_of_a_local_module_removes_the_star_statement`,
which holds either way. What is not: what the uses become.

### F23 — D9 and D19 still describe the rebinding mechanism F13 removed

Four places, all of which an implementer reading the spec top to bottom will
trip over. This is a repair list rather than a question — the human's answer is
the decision, these are the places that have not caught up with it.

1. **D9, the local bullet** — "the importing file gains a rebinding: `count =
	 helper__count`". There is no rebinding. Under the ruling the file's block has
	 no added statement at all.
2. **D9, the non-local bullet** — "the statement stays, with the bound name
	 aliased: `from pathlib import join as A__join`". It does not stay; it
	 becomes `import pathlib`, because `join` is now reached as `pathlib.join`.
3. **D9, the second paragraph** — "A name imported into a file becomes that
	 file's global, so R3's prefix applies to it." It does not become a global.
	 It is a use, and the name that carries the prefix is the one the value came
	 from.
4. **D9, the divergence note and D19's fourth bullet** — the root-level rebinding
	 collision (`from local_func import math` writing `math = local_func__math`).
	 There is no such statement, so the collision it describes cannot happen, and
	 with it the only collision D19 gives where the root's empty prefix is the
	 cause.

D19's *exception* paragraph survives and is now the only statement of the
non-local name-import rule: "A non-local **name** import is aliased to the
importing file's prefixed global — `from pathlib import join as A__join`". The
mechanism is the same and the conclusion changes — there is nothing to prefix,
so it becomes `pathlib.join`. That is what
`test_a_name_import_from_a_non_local_module_binds_an_unprefixed_name` pins.

### F24 — two name-import shapes with no stated answer

Both are real code, and both produce a silently broken bundle rather than an
error.

**A name the module does not define.** `from helper import thing`, where
`thing` is something `helper` itself imported. The bundler checks whether the
target is a file; it is not; so it takes the name branch and rewrites every use
of `thing` to `helper__thing`. Nothing defines that, because `thing` is a
non-local module name and D19 leaves those unprefixed. D9 already has a stated
limit of exactly this shape for star imports — its divergence note, "rebinding
are emitted for the inlined module's defined globals only" — so the name-import
case needs the same sentence or a ruling that it behaves differently.

**A name imported at function scope.** `from helper import count` inside a
function. D9's ruling is phrased about what a name imported *into a file* is
reached through, and does not say whether function scope changes it. If it does,
the name is in the enclosing scope's rename table and the function's uses
resolve; if it does not, the use is rewritten to `helper__count` and resolves
anyway. Both readings happen to work, which is why this one is cheap to answer
and expensive to leave.

## Closed, and where each answer went

| Flaw | Ruling | Where it lives |
|---|---|---|
| F13 | No rebinding. `y` a file → `import x.y`; `y` a name → every use is `x.y`. Either lands at `x__y`. | `TestNameImportsD9`, rewritten. Spec repair is F23 |
| F14 | The program name does not matter to the caller, only to `cli`'s signature | Proceeding with arguments-only — see below |
| F15 | A missing input file is a cli error | `test_an_input_path_that_does_not_exist_returns_one`, `test_an_output_path_that_cannot_be_opened_returns_one` |
| F16 | Dictionaries; propose the names | `TestStatementShapeD16`; the two names are in the table above |
| F17 | Empty lines and comments pass through | `TestNonNameTextSurvivesR7` and `TestNonCodeLinesAreKeptD18` |
| F18 | not answered | `test_indented_local_import_leaves_a_pass_where_it_was` uses the form both readings agree on |
| F19 | not answered | requirement with no derivable test |
| F20 | answered by F13 — `y` a file is `import x.y`, which is R3's reading, so R3's worked example holds | `test_a_relative_import_reference_uses_the_full_modpath_prefix` |

**On F14**, since the answer was a question back: it does not matter to the
person running the bundler, who types `python3 pybundle.py --in ...` once and
forgets it. It matters only to what the `__main__` block hands `cli`. The suite
proceeds with **arguments only** — `cli(sys.argv[1:])`, so
`cli(["--in", p, "--out", "-"])` — because that is what `argparse.parse_args`
takes, and because "commandline args for parameters" describes `argv` as the
parameters. If the implementation uses `argparse`, the choice is made for it and
this clause in D13 is belt and braces. Ruling the other way is one literal per
test: sixteen of the eighteen CLI tests gain a name at the front, and
`test_no_arguments_returns_one` still passes either way.

**On F17**, the ruling is recorded in the tests, and one clause would put it in
the spec so an implementer does not read D1 narrowly: *an empty line and a
comment-only line are passed through unchanged; the rules about what a statement
is exist so a multi-line statement is not broken apart, not so that anything is
removed.*

## Blocked and not written

| Requirement | Blocked by | What is missing |
|---|---|---|
| D9 what a star import of a local module's uses become | F22 | rename table, or the rebindings F13 removed |
| D9 a name the imported module does not define | F24 | whether it is the stated star-import limit, or something else |
| D9 a name imported at function scope | F24 | whether the rewrite crosses into the enclosing scope |
| D2 a function-local name import | F19 | the same question as the row above |
| D8 one entry per import statement, in source order | F16 | nothing — observable behaviourally, which is why it is not listed as blocked elsewhere |
| D11 `inline` on a nested file | F21 | whether a modpath is dotted or slashed |

Every requirement, decision and error in the spec is either covered in the
traceability table above or listed here. Nothing is untested and unaccounted
for.

## Blocked and deliberately not written

- **D7's excluded-on-purpose list.** Dynamic imports, circular-import problem
	detection, collision detection. Each is a thing the bundler does not do; a
	test would assert the absence, which the spec does not ask for.
- **Edge cases: errors in source.** Excludes a class of behaviour rather than
	stating one.
- **The exact text of a diagnostic.** D14 says where each of the three goes and
	that all three exist. Nothing states what they say, so the tests assert that
	stderr is not empty, or — where it matters — that stdout equals the bundle byte
	for byte.
- **What the missing-file error prints.** F15 settles the exit code. Whether
	anything is written to stderr for it is still open, and no test depends on it.

## A correction to the first derivation

`pybundle-tests-pass1.md` carries a blocking count that does not reconcile, and
the spec's *Open, and deliberately so* section says so. Here is the count, with
the arithmetic shown.

| Group | Flaws | Count |
|---|---|---|
| Blocked tests entirely — no test could be written at all | F4, F5, F6, F7, F8, F12 | 6 |
| Blocked direct tests only — resolved for the suite by a stated workaround, not by a decision | F1, F2, F3 | 3 |
| Needed no decision to proceed | F9, F10, F11 | 3 |
| | | **12** |

The "nine" came from counting F1, F2 and F3 individually as blocking while
labelling them "blocking for direct tests only". The "seven" counted F1–F3 as
one entry in the list of what to do next. Both counted the same twelve
differently. Six is the number that describes what actually stopped the work.

## What the human has to do

1. F23, so D9 and D19 stop describing a mechanism that no longer exists. This is
	 the one with teeth: an implementer reading the spec top to bottom today will
	 build the rebindings.
2. F22 and F24, if a star import of a local module or a function-scope name
	 import is going to work.
3. F18, F19 and F21 if they are — all three are cheap and none blocks.
4. Sign off on the tests, or tell me which derivation to redo.
