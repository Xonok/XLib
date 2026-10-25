# pybundle — pass 1, third derivation

**2026-10-15.** Re-derived against `tools/pybundle/SPEC.md` after the *Decisions —
2026-10-15, after test pass 2* section (D20–D25). **176 tests in five files**, up
from 138, superseding `pybundle-tests-pass1-2.md`.

The tests compile and are clean under xlint. They do not run: there is no
implementation, which is the state this stage is supposed to be in.

**D20 reversed D9**, and D9 had grown into the mechanism the import tests were
written against. This is therefore a re-derivation rather than an edit: two classes
are gone, four replace them, and two are new for D21 and D23. Seven spec flaws,
listed below; two of them change tests that already existed.

## What the new decisions changed

| Decision | Effect on the suite |
|---|---|
| **D20** every import rebinds | `TestNameImportsD9` (11) and `TestNameCollisionsD19` (4) deleted. `TestNameImportsD20` (15), `TestStarImportsD20` (9), `TestNonLocalModuleImportsD20` (8) and `TestNameCollisionsD24` (4) replace them. Three of D8's mixed-statement tests rewritten, because a non-local target in a mixed statement is now aliased too |
| **D21** blocks tracked by INDENT/DEDENT | `TestBlocksTrackedByTokensD21` (2), new. No prior test could have failed on the withdrawn comparison |
| **D22** the leaves' shapes and three clauses | No test added; three docstrings rewritten, because they each still described an open question the section closed (F14, F16, F18) |
| **D23** the indentation warning | `TestIndentationWarningD23` (13), new — the diagnostic did not exist before |
| **D24** collisions under aliasing | `TestNameCollisionsD24` (4), replacing the D19 class |
| **D25** the blocking count | Nothing to test |

The count of files a test lives in is unchanged: five, split by module as before.

## The seven cases the spec says the tests must pin

D20 closes by naming them (SPEC.md:987-996). Each is pinned, and the trace is
here so the reader can check the claim rather than take it.

| The spec's case | Tests |
|---|---|
| `from helper import count` emits `A__count = helper__count`, and **nothing** rewrites the use | `test_a_local_name_import_emits_a_rebinding`, `test_a_name_imported_into_a_file_is_reached_through_that_files_own_name` — **the second does not agree with the first**, see F25 |
| `from pathlib import join` emits `from pathlib import join as A__join`, replacing the test that asserted `pathlib.join` | `test_a_non_local_name_import_is_aliased_to_the_importing_files_prefix`, `test_a_non_local_name_import_rewrites_its_use_to_the_alias` |
| `import email.utils` emits the statement **and** `A__email = email`, and both `A__email.utils.parseaddr` and `A__email.message_from_string` resolve | `TestNonLocalModuleImportsD20` — 4 tests; the two reach the parent and the leaf separately, because D20 calls the half-silent failure the dangerous one |
| a local star import followed by a shadowing definition resolves to the shadow | `test_a_star_import_followed_by_a_shadowing_definition_gives_the_shadow` — runs the bundle, because the emitted text is identical whether the rebind comes before or after the shadow |
| a name import at function scope stays function-local | `test_a_name_import_at_function_scope_rebinds_where_it_was_written`, `..._rewrites_its_use_inside_the_function`, `..._stays_function_local` |
| the indentation warning fires on the four conditions and not on the two excluded, first offending line named per file | `TestIndentationWarningD23` (13) |
| `NOT_A_MODULE` stays retired, `RELATIVE_IMPORT_IN_ROOT` stays in `inline` | `TestErrors`, whose docstring names the retirement |

## The three bundles that are actually run

D20 is the only requirement whose emitted text cannot be read on its own. A rebind
and a use that disagree with each other look exactly like a correct pair written
down — both lines are present, in a plausible order, and the bundle raises
`NameError` when imported. So three tests run the finished bundle rather than
reading it, and they are the three cases the spec itself verified against real
python:

| Test | Bundle gives | Why the text cannot say so |
|---|---|---|
| `test_a_star_import_followed_by_a_shadowing_definition_gives_the_shadow` | `2` | A rebind flushed at the end of the file gives `1`, and both files contain the same two assignment lines |
| `test_a_name_import_at_function_scope_stays_function_local` | `1` | The rebind is present at the right indentation either way; what differs is whether the use names it |
| `test_a_local_name_import_binds_the_value_the_callee_defined` | `1` | Same, at module scope |

All three were checked by hand against real python before being written down. The
first is the sharpest: I ran the variant where the use is left pointing at the
callee's global, and it gives `1`.

## Traceability

Every requirement in the spec, and what tests it. The five files are `test_bundler`
(main and `inline`), `test_bundler_names`, `test_bundler_source`, `test_bundler_cli`
and `test_bundler_structure`.

| Spec | Tests |
|---|---|
| R1.1 root folder is the entry's parent | `TestInliningR1` throughout — every fixture's root folder is the entry's parent |
| R1.2 local iff in the root folder or below | `test_module_in_the_root_folder_is_inlined`, `test_module_in_a_subfolder_is_inlined`, `test_file_outside_the_root_folder_is_not_inlined`, `test_file_outside_the_root_folder_is_left_as_a_normal_import`, `test_a_local_file_shadows_a_standard_library_name` |
| R1.3 every import checked, local ones inlined | `test_indented_local_import_is_inlined_even_under_a_false_condition`, `test_a_local_file_shadows_a_standard_library_name` |
| R1.4 imports placed before the file's own code | `test_imported_code_is_written_before_the_importing_file`, `test_circular_import_raises_nothing`, and every `_start_comments` equality, which pins order |
| R1.5 non-local imports stay where they were | `test_non_local_import_stays_between_its_own_neighbours`, `test_indented_non_local_import_stays_indented`, `test_a_non_local_import_statement_is_never_removed` |
| R1.6 second reference dropped | `test_second_reference_to_a_module_is_dropped`, `test_a_dropped_import_leaves_nothing_behind`, `test_a_dropped_second_reference_writes_a_message_to_stderr`, and `test_two_files_importing_the_same_name_both_rebind_it` — the rebind has to survive the dropped block |
| R1.7 root seeded into the handled set | `test_module_importing_the_root_emits_the_root_once_and_last` |
| R2 ordering and the comment pair | `TestOutputCommentsR2` (5), and every `_start_comments` assertion elsewhere |
| R3 prefix is the flattened path below the root | `test_module_global_is_prefixed_with_the_file_prefix`, `TestPrefixApplied` (3), `TestNonAsciiNames` (1), `test_init_file_globals_are_prefixed_with_its_own_component` |
| R3 module names treated as full modpaths | `test_a_relative_import_reference_uses_the_full_modpath_prefix`, `test_a_reference_through_a_module_name_becomes_the_prefixed_global`, `test_an_aliased_import_reaches_the_same_renamed_global` |
| R3 leading underscores move in front | `TestLeadingUnderscores` (5), `test_private_global_keeps_its_underscores_in_front_of_the_prefix` |
| R3 the root's own names exempt, and only those | `test_root_own_definitions_are_not_translated`, `test_a_sibling_in_the_root_folder_is_translated_even_beside_the_root` |
| R4 scope-aware, function and class | `TestScopeR4` (14) |
| R4 `global` renames and does not block | `test_global_name_is_translated_with_the_file_prefix`, `test_global_statement_names_are_translated_too` |
| R4 `nonlocal` does neither | `test_nonlocal_name_is_neither_translated_nor_blocked` |
| R5 anything file-like, one code path | `test_a_file_sink_produces_the_same_bytes_as_a_buffer`, `test_a_real_pipe_produces_the_same_bytes_as_a_buffer`, `test_the_bundle_cli_writes_is_the_bundle_main_writes` |
| R5 never closes a sink it did not open | `test_a_buffer_the_bundler_was_given_is_not_closed`, `test_a_file_the_bundler_was_given_is_not_closed`, `test_the_out_file_holds_the_whole_bundle` |
| R6.1 no parse tree | `test_no_module_of_the_bundler_imports_ast` |
| R6.2 state piped, never global | `test_a_run_after_another_matches_the_same_run_alone` |
| R6.3 nothing imports the entry file | `test_only_the_entry_module_imports_the_other_modules` |
| R7 only names are rewritten | `TestNonNameTextSurvivesR7` (3), `TestNonCodeLinesAreKeptD18` (3) |
| D1 statements, not lines | `TestStatementBoundariesD1` (8), `TestStatementShapeD16` (7), `TestEmptyInput` (1), `test_dict_continuation_lines_do_not_bind_names_in_the_function`, `test_a_multiline_string_containing_a_def_does_not_open_a_block`, and every `TestScopeR4` binding form |
| D2 blocks by indentation, nested blocks stack | `test_nested_function_inherits_the_outer_block` |
| D2 binding forms | the nine `TestScopeR4` forms, plus the function-local name import D20 adds — `test_a_name_import_at_function_scope_rebinds_where_it_was_written`. F19 is therefore closed |
| D3 the root exception is the empty prefix | `TestRootIsTheEmptyPrefix` (2) |
| D4/D12 the function set and its file per function | `test_each_function_of_the_set_lives_in_the_file_the_table_names` |
| D5/D12 call graph — `main` and `inline` | every test in `test_bundler.py` drives `main`; `TestInlineD11` (3) drives `inline` |
| D6 `__init__.py` is an ordinary component | `test_init_file_contributes_its_own_name_as_a_path_component`, `test_init_file_globals_are_prefixed_with_its_own_component` |
| D6 `import x as y` reaches the same place | `test_an_aliased_import_reaches_the_same_renamed_global`, `test_an_aliased_dotted_import_is_aliased_rather_than_kept` |
| D6 relative imports resolve; the root may not | `test_a_relative_import_reference_uses_the_full_modpath_prefix`, `test_a_relative_import_in_the_root_file_raises`, `test_a_relative_import_in_a_non_root_file_does_not_raise` |
| D7 staged vs excluded | the staging list is empty as of D9; nothing to test |
| D7 excluded on purpose | not tested, deliberately — see *Blocked and deliberately not written* |
| D8 an inlined import's statement is removed | `test_an_entirely_local_import_statement_is_removed`, `test_a_local_name_import_removes_its_statement`, `test_a_local_star_import_removes_the_star_statement` |
| D8 a mixed statement keeps the non-local half | `test_a_mixed_import_statement_keeps_the_non_local_half`, `test_a_mixed_import_statement_loses_the_local_half`, `test_a_mixed_statement_keeps_the_remaining_targets_in_source_order` |
| D8 one entry per import statement, in source order | pinned behaviourally by the block order every `_start_comments` assertion fixes; no direct test, because D8 names no fields for an entry (see *Known limits*) |
| **D20 local name import** | `test_a_local_name_import_emits_a_rebinding`, `test_a_rebinding_follows_the_block_that_defines_what_it_reads`, `test_a_local_name_import_binds_the_value_the_callee_defined`, `test_an_indented_name_import_rebinds_at_that_indentation` |
| **D20 non-local name import** | `test_a_non_local_name_import_is_aliased_to_the_importing_files_prefix`, `test_a_non_local_name_import_rewrites_its_use_to_the_alias` |
| **D20 non-local module import** | `test_a_non_local_module_import_is_aliased_to_the_importing_files_prefix`, `test_a_use_of_a_non_local_module_import_goes_through_the_alias` |
| **D20 dotted import** | `test_a_dotted_import_keeps_its_statement`, `test_a_dotted_import_adds_a_rebind_for_the_name_python_actually_binds`, `test_the_dotted_rebind_follows_the_statement_that_binds_it`, `test_a_use_that_reaches_past_the_leaf_goes_through_the_parent`, `test_a_use_of_the_dotted_imports_own_parent_is_reachable` |
| **D20 local star import** | `test_a_local_star_import_rebinds_a_defined_global`, `test_a_local_star_import_rebinds_a_defined_function`, `test_a_star_imported_name_is_used_through_the_importing_file`, `test_a_star_import_followed_by_a_shadowing_definition_gives_the_shadow` |
| **D20 the rebind's LHS is not prefixed again** | `test_a_rebinding_left_hand_side_is_not_prefixed_again`, and the three function-scope tests. `test_name_carrying_an_existing_prefix_is_prefixed_again` pins that `renamed` itself is *not* where the exemption lives |
| **D20 a rebind travels with its import** | `test_the_rebinding_follows_the_block_that_defines_what_it_reads`, `test_the_dotted_rebind_follows_the_statement_that_binds_it` |
| **D20 a star import is a name import** | the two shadowing tests together — the second is D20's reason for the rule, and the first is the consequence |
| **D20 a name the module did not define** | `test_a_name_the_module_did_not_define_reaches_the_callees_own_import` |
| **D20 the surviving divergence** | `test_a_local_star_import_does_not_rebind_a_name_the_module_imported`, `test_an_explicit_import_still_reaches_a_name_the_module_imported` |
| D9's non-local star import, kept | `test_a_star_import_of_a_non_local_module_is_left_in_place`, `test_a_star_import_of_a_non_local_module_warns` |
| **D21 blocks by INDENT/DEDENT** | `TestBlocksTrackedByTokensD21` (2) |
| D22 `statements` returns `text` and `indent` | `TestStatementShapeD16` (7) |
| D22 `cli(argv)` takes argv | `test_bundler_cli.py` — every call passes arguments only |
| D22 empty and comment-only lines pass through | `TestNonCodeLinesAreKeptD18` (3) |
| D22 an indented local import leaves a `pass` | `test_indented_local_import_leaves_a_pass_where_it_was`, `test_an_indented_name_import_rebinds_at_that_indentation` |
| D13 the command line | `TestSuccess` (3), `TestStdoutSink` (4), `TestUsage` (8), `TestBundlerErrors` (3) |
| D14 diagnostics to stderr, none to the sink | `TestDiagnosticsGoToStderrD14` (3), `test_a_diagnostic_warns_on_stderr_while_stdout_carries_only_the_bundle`, `test_usage_is_printed_on_stderr`, `test_usage_is_not_printed_on_stdout`, `test_a_dropped_second_reference_writes_nothing_to_stdout` |
| D15 the two remaining errors | `TestErrors` (4), `test_a_bundler_error_is_reported_on_stderr`, `test_a_relative_import_in_the_root_returns_one` |
| D16 the leaves' return shapes | `TestTranslateD16` (5), `TestStatementShapeD16` (7), `TestStatementBoundariesD1` (8), `TestEmptyInput` (1) |
| D17 bare module references | `TestBareModuleReferencesD17` (2) |
| **D23 anchor** | `test_a_file_whose_indentation_type_differs_from_a_space_root_is_reported`, `test_a_file_whose_indentation_type_differs_from_a_tab_root_is_reported`, `test_a_file_whose_indentation_matches_the_root_is_not_reported`, `test_a_root_without_indentation_reports_nothing_when_the_files_agree`, `test_a_root_without_indentation_still_reports_files_that_disagree` |
| **D23 trigger** | the two above, plus `test_a_line_carrying_both_indentation_types_is_reported` |
| **D23 ignored** | `test_a_whitespace_only_line_of_the_other_type_is_ignored`, `test_a_multiline_string_interior_of_the_other_type_is_ignored`, `test_a_bracket_continuation_line_of_the_other_type_is_ignored` |
| **D23 report** | `test_the_report_names_the_first_offending_line`, `test_the_report_does_not_name_a_later_offending_line`, `test_a_file_with_two_offending_lines_is_reported_once` |
| **D23 never refuse** | `test_a_mixed_convention_tree_is_bundled_anyway` |
| **D24 the three prevented sources** | `test_a_name_aliased_in_the_first_file_takes_that_files_prefix`, `test_the_same_name_aliased_in_the_second_file_takes_its_own_prefix`, `test_a_root_level_rebinding_is_unprefixed_beside_another_files_prefix` |
| **D24 the survivor** | `test_a_star_import_of_a_non_local_module_warns`, and `test_a_collision_between_two_aliased_imports_is_not_warned_about` for the declined warning staying declined |
| D18 / R7 non-name text survives | `TestNonNameTextSurvivesR7` (3), `TestNonCodeLinesAreKeptD18` (3) |
| Edge case: conditional imports | `test_indented_local_import_is_inlined_even_under_a_false_condition`, `test_indented_local_import_leaves_a_pass_where_it_was`, `test_indented_non_local_import_stays_indented` |
| Edge case: circular imports | `test_circular_import_raises_nothing` |
| Edge case: name collisions | `TestNameCollisionsD24` (4) |
| Edge case: errors in source | not tested — it excludes a class of behaviour rather than stating one |

The other direction: every test maps to a row above. The exceptions are the seven in
*Blocked and not written*, and none of them is a test that exists without a
requirement behind it.

## Spec flaws

Seven. Two of them change tests that existed before this pass, which is the part
worth reading twice.

### F25 — "nothing rewrites the use" contradicts D20's own verification

**Blocking: three tests ride on it.** D20's closing bullet says `from helper import
count` emits `A__count = helper__count`, **and nothing rewrites the use**.

Taken literally that makes the bundle raise `NameError`. I traced it: the rebind
binds `sub__client__count`; a use of `count` left alone looks for `count`, which
nothing defines in the bundle, because the only rebind D20 emits for a local name
import is the prefixed one. The other reading — the use becomes
`sub__client__count`, and what is *not* done is pointing it at `helper__count` — is
the one D20's verified table requires, because the function-scope case is recorded
as giving `1` and it cannot give `1` unless the use names the rebind.

I derived the tests from the verification rather than the bullet, and I checked
that reading against real python before writing it down: the three bundles below
are the spec's three verified rows, built by hand and run.

| Spec's row | Test | Result |
|---|---|---|
| star import then shadowing → `2` | `test_a_star_import_followed_by_a_shadowing_definition_gives_the_shadow` | 2 |
| name import at function scope → `1` | `test_a_name_import_at_function_scope_stays_function_local` | 1 |
| name the module did not define → resolves | `test_a_name_the_module_did_not_define_reaches_the_callees_own_import` | — (text) |

**What is needed:** the bullet reworded to say the use is reached through the
importing file's own prefixed name, and that what F13's mechanism did — pointing
it straight at the callee's global — is what no longer happens. As written, an
implementer following the bullet literally writes a bundler whose bundles raise
`NameError`, and it is the kind of bug that passes a text-level test.

### F26 — a local module import has no row in D20's table

**Blocking: five tests that already existed assert the reading I chose.** The table
has five rows — local name import, non-local name import, non-local module import,
local star import, dotted import. None of them is a plain local module import.

The general condition covers it and makes it worse: *"the alias rule applies except
where python binds a name the statement does not spell"*. `import helper` spells
`helper`, so the alias rule applies, and `import helper as A__helper` would have to
bind the module object — which D17 says exists under no name at all, because
inlining prefixes names rather than constructing objects. The same applies to
`import helper as h`, to `import helper.sub` (which binds `helper`, the one case the
dotted rule *does* cover, but the callee is local so nothing binds it), and to a
name import whose target is a local module, `from helper import nested`.

So the table's condition cannot be applied to these four shapes, and nothing states
what happens instead. I read them as **no rebind, and the use goes straight to the
prefixed global**, because that is the only reading in which the bundle works, and
because D17 already says the module object is not there to bind. Five existing
tests assert it: `test_a_reference_through_a_module_name_becomes_the_prefixed_global`,
`test_an_aliased_import_reaches_the_same_renamed_global`,
`test_a_from_import_of_a_module_is_the_module_path` (rewritten below, so two), the
two in `TestBareModuleReferencesD17`.

**What is needed:** a row or a sentence saying a local module import emits no
rebind, because there is nothing to bind.

### F27 — the empty-prefix form of an aliased import in the root

**Not blocking; no test written.** D20's rows are written with a non-empty prefix
(`A__math`). In the root the prefix is empty (D3), so `import math` becomes either
`import math as math` under the uniform rule, or `import math` unchanged under D3's
own principle that translating a name with an empty prefix is a no-op. D3 has a
precedent for the no-op reading and D20's table has none for it.

Every test that would read it out is written in a non-root file for this reason.
`test_a_non_local_import_statement_is_never_removed` and
`test_non_local_import_stays_between_its_own_neighbours` assert substrings that
hold under either form, so they are not evidence either way.

**What is needed:** one clause. The choice costs the bundler nothing and the reader
a line of spec.

### F28 — D20's `A__Path = server__Path` cannot be reproduced

**Not blocking.** The worked example says `from helper import Path`, where `Path` is
`helper`'s own non-local import, "becomes `A__Path = server__Path`". The prefixing is
by the defining module, so a name reaching `helper` is `helper__Path`; `server__`
is the prefix of a file the example never names. The mechanism in the sentence is
right and is what the test uses; the literal is not.

**What is needed:** a corrected example, or the sentence without it.

### F29 — D23's report format: the line's text or its number

**Blocking: three tests ride on it.** D23 says the report is *"one entry per
offending file, naming that file's **first** offending line"*. That fixes the
content — a file, and a line, and which line — but not the form. Three tests read
it as quoting the line, because quoting is what makes a line findable by reading
the message, and because D23's own reason ("good enough, since this is generally not
the bundler's purpose") reads like a human skimming output rather than reading
numbers off it.

If you mean the line **number**, these three change and nothing else does:

| Test | now asserts | would assert |
|---|---|---|
| `test_the_report_names_the_first_offending_line` | the first line's text is in stderr | the first line's number is |
| `test_the_report_does_not_name_a_later_offending_line` | the second's text is not | the second's number is not |
| `test_a_file_with_two_offending_lines_is_reported_once` | that text appears once | that number appears once |

The other ten tests in the class ask only whether the warning fires, and assume
nothing about the form.

**What is needed:** "the text of the line" as a clause, or the number.

### F30 — the anchor when the root file mixes both indentation types

**Not blocking; no test written.** D23 anchors on *"the convention of the root
file"*, and a root with one space-indented block and one tab-indented block has two.
Which is the anchor, and is the root then reported as an offending file against its
own anchor, are both unstated. Nothing in the spec needs an answer, so I wrote no
test rather than invent one — but an implementer will hit it the first time they
bundle a file that mixes, which is the case D23 exists to warn about.

**What is needed:** a clause, or a sentence saying it is unhandled.

### F31 — in what order is "the first file that has indentation"

**Not blocking; the tests are written to not care.** D23's fallback anchor is "the
first file that has indentation", and the spec does not say whether that means the
first in bundle order, the first in import order, or the first by path. The two
tests that exercise the fallback are arranged so all three readings agree — the
files are named so that the one the bundler reaches first is also the one a reader
names first — so they pin the rule and not the order.

**What is needed, if you want it pinned:** "the first file inlined".

## Blocked and not written

| Requirement | Blocked by | What is missing |
|---|---|---|
| D20 a local module import's rebind | F26 | a row or a sentence; four shapes are affected |
| D20 whether a use of a name-imported name is rewritten | F25 | the bullet contradicts the verification table |
| D23 the content of the report | F29 | line text or line number |
| D23 the anchor when the root mixes | F30 | a clause, or "unhandled" |
| D21 an `inline` call on a nested file | F21 | still open from the last pass: is a modpath dotted (`py.command.api`, R3) or slashed (joined to a folder, D12)? |
| D9 a name import whose target is a local module | F26 | the same missing row |

## Blocked and deliberately not written

- **D7's excluded-on-purpose list.** Dynamic imports, circular-import problem
	detection, collision detection. Each is a thing the bundler does not do; a test
	would assert an absence the spec does not ask for.
- **Edge cases: errors in source.** Excludes a class of behaviour rather than
	stating one.
- **The exact wording of three of the four diagnostics.** D14 says where they go and
	that they exist. D23 says more, which is why three tests in that class do read the
	message.
- **The missing-file error's output.** F15 settled the exit code; whether anything
	is written to stderr for it is still open, and no test depends on it.

## Known limits of this suite

- **`imports`' return shape has no field names.** D8 fixes what an entry carries —
	the statement, its kind, its targets, whether it was relative — and D22 fixed
	`statements`' two names but says nothing about these four. So `translate` cannot
	be called directly in any test that needs a `resolved` value: constructing one
	would mean inventing four names. Every D20 test is therefore driven through
	`main`. This was a deliberate choice in the last pass and D20 has not revisited it.
- **F19 is now closed.** D2's binding-form list was missing the function-local name
	import, and D21 adds it. The test that pins it is
	`test_a_name_import_at_function_scope_rebinds_where_it_was_written`, and F19 can
	come off the list.
- **D24 leaves the declined collision warning to the implementer.** Whether D19's
	paragraph survives is editorial, and the suite passes either way:
	`test_a_collision_between_two_aliased_imports_is_not_warned_about` asserts nothing
	is written, which is what happens under both readings.

## Checks run

- All five files compile (`python3 -m py_compile`).
- xlint is clean over all five (`xlint tools/pybundle/test/*.py`
	→ `clean`). Note it only sees them because the paths are explicit — directory
	traversal skips any path part named `test`, which is `AK633QC`.
- **Every fixture body in the suite compiles as python** — 203 of them, checked
	mechanically from the AST rather than by reading. A fixture the bundler cannot
	read would let any implementation pass the test that uses it.
- The D21 fixture was verified to be the case it claims: python compiles it,
	`tokenize` accepts it, and the two block-tracking readings actually disagree on it
	(tokenizer says `value = 1` is inside `outer`; string comparison says module
	scope). A tab body directly under a space opener is **not** usable — python's
	tokenizer raises `TabError` on that input before block tracking is asked anything,
	which is worth knowing because D21's prose uses it as the example.

## What the human has to do

1. **F25.** The bullet and the verification table disagree, and only one of them
	produces a working bundler. This is the one with teeth.
2. **F26.** Four import shapes have no row, and five existing tests already assume
	an answer.
3. **F29.** Line text or line number; three tests turn on it.
4. **F27, F28, F30, F31** if they are — all four are cheap and none blocks.
5. **Sign off on the tests**, or tell me which derivation to redo.

On (5): the suite is not a smaller version of the last one. It is 176 tests against
a spec whose import mechanism was reversed four days after the last derivation, and
the reversal is the kind that moves assertions rather than adding them — 15 tests
gone, 36 written, 2 new classes for decisions that had no test at all before today.
