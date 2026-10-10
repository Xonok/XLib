# Plan: Investigating Control Over AI-Authored Code

## Background

XLib is developed with heavy AI agent involvement (opencode agents, multiple workers). The human handles design decisions but the implementation is largely AI-written. This creates a control problem: the human needs deep familiarity with the codebase to find design flaws, but AI-written code is structurally unfamiliar in a way that makes reading and reviewing difficult.

**Core tension**: AI flaws are silent (they compile, they run, they even pass tests — but the logic or design may be subtly wrong). The human needs a second way of verifying correctness beyond "it seems to work."

### Specific problems identified

1. **Random-access comprehension**: Can't look at a random point in the code and understand what's happening.
2. **Big-picture ignorance**: Don't know the architectural ways a library works beyond its general purpose.
3. **Review friction**: Finding design flaws requires reading everything, but unfamiliar code is slow to read.
4. **Silent failure mode**: AI code often works by coincidence rather than by design, and no test catches the gap.
5. **Documentation isn't free**: Excessive documentation is no easier to read than the code itself.

## What this plan investigates

Whether AI-heavy development can be made viable long-term by combining several mechanisms that together give the human enough legibility to maintain real control. This isn't about reducing AI involvement — it's about making it survivable.

## Investigation steps

### Phase 1: Assess current state

- [ ] Audit a representative library (e.g. `csv` or `net5`) to characterize how AI-authored code currently looks:
	- Module structure consistency (do modules follow the same patterns?)

	- Naming consistency (are similar concepts named similarly across the codebase?)

	- Are there ad-hoc patterns that differ between modules written at different times?

	- How much implicit knowledge is required to understand a module?

- [ ] Check current documentation state:
	- Which libraries have architectural docs? Which don't?

	- What does a module-level docstring look like in practice?

	- How do tests read — are they scenario-oriented or unit-focused?

- [ ] Review AGENTS.md rules and existing code style enforcement:
	- Which rules currently exist?

	- Which rules are enforced by xlint vs. just guidelines?

	- Which of the proposed mechanisms from Phase 2 overlap with existing rules?

### Phase 2: Design candidate mechanisms

The previous discussion identified these candidates. Each needs to be concretized into something that can be added to the project's rules or tooling:

**Mechanism A: Per-library architectural documentation**
- What: A short document (in the dev folder) describing the library's module structure, data flow, key invariants, and design decisions. NOT line-by-line comments.
- Purpose: Gives a map before you navigate. Addresses problem #2 (big-picture) and partly #1 (random-access).
- Questions to answer:
	- How long should it be? (Target: <100 lines per library)

	- What format? (Markdown in dev folder? Module-level docstrings? Both?)

	- How does it stay current? (Who updates it — agents on change, or human periodically?)

	- Is this redundant with existing AGENTS.md project-level docs?

**Mechanism B: Structural consistency rules**
- What: Enforce consistent patterns across modules so that once you learn one module, you can scan others faster.
- Purpose: Addresses problem #1 (random-access comprehension) by making code predictable.
- Questions to answer:
	- What patterns should be consistent? (Entry point structure, error handling, import conventions)

	- Which of these are already in AGENTS.md? Which need adding?

	- Should xlint enforce structural consistency, or just guidelines?

**Mechanism C: Scenario-oriented tests**
- What: Tests organized around user-facing scenarios rather than internal function boundaries.
- Purpose: Addresses problems #3 (review friction) and #4 (silent failure). Tests serve as executable documentation.
- Questions to answer:
	- How are tests currently structured in this project?

	- What would "scenario-oriented" look like in practice for XLib's libraries?

	- Is there a testing framework in use, or is it ad-hoc?

**Mechanism D: Design review step**
- What: Before implementation, produce a brief design doc (module split, key data flows, assumptions). Human reviews the design, not every line of code.
- Purpose: Addresses problems #3 and #4 by catching design flaws before they become code.
- Questions to answer:
	- How does this interact with the current workflow?

	- Should design docs be per-library or per-feature?

	- How detailed should they be?

**Mechanism E: Subtle-behavior annotations**
- What: Agents annotate (briefly) when code works in a non-obvious way — edge cases, ordering dependencies, coincidental correctness.
- Purpose: Addresses problems #1 and #4 directly.
- Questions to answer:
	- How to avoid turning into excessive documentation?

	- Should this be a rule in AGENTS.md or a softer guideline?

	- Are there existing examples of this in the codebase?

### Phase 3: Evaluate and prioritize

- [ ] For each mechanism, estimate:
	- Implementation cost (how much rule/tooling change?)

	- Maintenance cost (how much ongoing effort?)

	- Legibility gain (how much does it help the human?)

	- Risk of staleness (how quickly does it go out of date?)

- [ ] Identify which mechanisms are independent (can be adopted separately) vs. which reinforce each other
- [ ] Determine which mechanisms should be tried first (lowest cost, highest legibility gain)

### Phase 4: Prototype and validate

- [ ] Pick 1-2 mechanisms to trial on a single library
- [ ] Have agents follow the new rules during development
- [ ] After a development cycle, evaluate: did the human find the code more legible? Did review catch more issues? Was maintenance overhead acceptable?
- [ ] Iterate on the mechanism based on what was learned

## Key constraints

- This project already has a working development workflow (opencode agents, bundler, release script, xlint). Any new mechanism must integrate with it, not fight it.
- The human values conciseness. Rules and documentation that are verbose or bureaucratic will be ignored.
- The project is real and active. Investigations should not block ongoing development.
- Multiple agents may work concurrently. Mechanisms must work across agent sessions (stateless or persisted in files).

## Open questions for the other agent

- Look at 2-3 libraries in this repo and characterize: how legible is the code today? Where does it hurt most?
- Look at the test situation: what tests exist, how are they structured, what's the coverage like?
- Look at the existing rules in AGENTS.md and assess: which of the proposed mechanisms are already partially covered?
- Are there patterns in the codebase (good or bad) that suggest which mechanisms would have the most impact?

## Success criteria

After this investigation, we should be able to say:
1. Which mechanisms are worth adopting and in what order.
2. What concrete changes to AGENTS.md, xlint, or agent prompts would implement them.
3. What the expected ongoing cost is.
4. Whether this makes AI-heavy development viable long-term, or whether there's a fundamental limit we're hitting.
