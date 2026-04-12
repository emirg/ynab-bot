# Documentation Workflow

This document defines how product and technical documentation is created before, during, and after implementation work.

It complements `docs/AI_WORKFLOW.md`:

- `docs/DOCUMENTATION_WORKFLOW.md` defines which documents exist, when they are required, and what each one means.
- `docs/AI_WORKFLOW.md` defines how approved work is executed, reviewed, and handed off.

---

## Core Documents

### 1. SPEC — What are we building?

The SPEC is the functional definition of a feature, system, or meaningful refactor.

It answers:

- What problem are we solving?
- What behavior is expected?
- What inputs, outputs, business rules, and edge cases matter?
- How will we know the work is correct?

The SPEC is intentionally implementation-agnostic. It describes behavior and constraints, not task sequencing or file-by-file edits.

### 2. PLAN — How will we build it?

The PLAN is the execution document derived from an approved SPEC.

It answers:

- What technical approach will be used?
- What steps must happen, and in what order?
- Which files, modules, tests, or manual prerequisites are involved?
- How will progress be tracked safely through implementation?

The PLAN must not duplicate the SPEC. It converts approved requirements into an implementation sequence.

### 3. ADR — Why did we choose this design?

An Architecture Decision Record captures significant, non-obvious, long-lived technical decisions.

It answers:

- What decision was made?
- What context led to the decision?
- What alternatives were considered?
- What consequences should future maintainers expect?

ADRs are historical memory. They are not planning artifacts.

---

## Required Order

The default workflow for non-trivial work is:

1. User request, roadmap item, or bug report
2. Draft `SPEC`
3. Review and approve the `SPEC`
4. Draft `PLAN` from the approved `SPEC`
5. Implement against the `PLAN`
6. Write `ADR` if a significant architectural decision was made or finalized
7. Review implementation, archive the `PLAN` and implemented `SPEC`, and update handoff state

Short version:

`SPEC -> PLAN -> IMPLEMENT -> ADR (if needed) -> REVIEW -> ARCHIVE`

---

## When Each Document Is Required

### SPEC

A SPEC is required for all future features and refactors.

For very small changes, the SPEC may be short, but it must still exist if the work changes behavior, interfaces, data flow, or user expectations.

Typical examples that require a SPEC:

- new feature
- behavior change
- API contract change
- meaningful refactor with observable risk
- new persistence or infrastructure behavior

### PLAN

A PLAN is required before implementation begins.

The PLAN must reference one approved SPEC and must be detailed enough that another engineer or agent can execute it without making missing design decisions.

### ADR

An ADR is required only for significant decisions, such as:

- choosing or replacing a framework or library
- changing architecture boundaries
- changing persistence or deployment strategy
- introducing a long-lived pattern, constraint, or compatibility policy

An ADR is not required for routine local implementation choices.

---

## Approval Gates

### SPEC gate

Implementation planning must not begin until the SPEC is considered approved by the active decision-maker in the session.

### PLAN gate

Code implementation must not begin until the PLAN is considered implementation-ready.

### ADR gate

An ADR does not need to exist before coding, but once a significant decision is made, the ADR must be written before the work is considered fully documented.

---

## Locations and Naming

Use date-based filenames for all three document types:

- `docs/specs/YYYY-MM-DD-feature-name.md`
- `docs/plans/YYYY-MM-DD-feature-name.md`
- `docs/adrs/YYYY-MM-DD-decision-name.md`

Templates live at:

- `docs/specs/_TEMPLATE.md`
- `docs/plans/_TEMPLATE.md`
- `docs/adrs/_TEMPLATE.md`

Completed implementation plans move to:

- `docs/plans/archive/`

Completed implementation specs move to:

- `docs/specs/archive/`

ADRs remain in place as project memory and must continue referencing the related PLAN and SPEC, even after the PLAN and SPEC have been archived.

---

## Language Rules

Documentation defaults to English.

Exceptions:

- user-facing copy, example commands, and UI text may remain in Spanish
- examples should preserve the project invariant that user-visible behavior is in Spanish

Do not mix languages randomly inside the same section when it reduces clarity.

---

## Document Boundaries

### SPEC should contain

- problem and motivation
- goals and non-goals
- expected behavior
- inputs and outputs
- business rules and invariants
- failure modes and edge cases
- acceptance criteria

### SPEC should not contain

- implementation step order
- task checklists
- commit strategy
- file move sequences unless the file structure is itself part of the requirement

### PLAN should contain

- source SPEC reference
- implementation approach
- dependency-safe task groups
- files or subsystems affected when needed
- explicit tests and verification
- rollout or manual prerequisites when relevant

### PLAN should not contain

- broad product rationale already captured in the SPEC
- architectural history that belongs in an ADR
- vague steps that leave decisions to the implementer

### ADR should contain

- decision
- context
- alternatives considered
- consequences
- references to the related SPEC, PLAN, and implementation

### ADR should not contain

- full implementation task lists
- generic architecture summaries unrelated to the decision

---

## Practical Workflow for AI Assistants

When the user asks to build something new:

1. Check whether a current SPEC already exists.
2. If not, create or refine the SPEC first.
3. Only after the SPEC is approved, create the PLAN.
4. Only after the PLAN is approved, implement.
5. If implementation locks in a significant design choice, write the ADR.
6. After review passes, archive the PLAN, archive the implemented SPEC, preserve ADR references to that archived PLAN and SPEC, and update `docs/wip_state.md`.

When the user asks to continue existing work:

1. Read `docs/wip_state.md`.
2. Identify the active SPEC and PLAN, if any.
3. If the SPEC or PLAN is stale, incomplete, or contradictory, fix documentation first.
4. Continue implementation only when the documentation state is coherent.

---

## Superseding Documents

If a newer SPEC replaces an older one:

- keep the older file for history
- mark the older file as superseded
- link the newer file from the old one

If an implementation PLAN becomes obsolete:

- replace it or archive it with a note explaining why

If a decision is reversed:

- do not edit the old ADR to erase history
- create a new ADR that supersedes the old decision
