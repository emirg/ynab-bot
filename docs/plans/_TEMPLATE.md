# Plan: [Feature/Refactor Name]

## Objective & Context
- **Status:** [Draft / In Progress / Completed]
- **Source Spec:** `docs/specs/[YYYY-MM-DD-feature-name].md`
- **Goal:** [1-2 sentences: What this implementation delivers]
- **Approach:** [Short technical summary derived from the approved spec]

## Affected Components
<!-- Only list the files or subsystems that matter for safe execution -->
- `path/to/file.py` — [what changes]

## Prerequisites (Manual)
- [ ] [Actions outside code: Env vars, API keys, infrastructure]

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

<!--
GROUPING RULES:
- Steps within the same group have NO dependencies between them → they run IN PARALLEL.
- Groups run SEQUENTIALLY — a group starts only after all prior dependencies complete.
- Each group (except Group 1) declares which groups it depends on.
- Two steps that modify the SAME FILE must be in different groups (sequential).
- DBA consultations go in their own group BEFORE the steps they inform.
- If a feature has no parallelizable steps, use a single group with all steps sequential.
- The PLAN must not restate the full product behavior from the SPEC. Only include implementation detail needed to execute safely.
-->

### Group 1
<!-- [What this group accomplishes] -->

#### [ ] Step 1: [Step Name]
- **Files:** `path/to/impl.py`
- **Action:** [Concise technical logic to implement]
- **Tests:** `path/to/test.py` — [Specific scenario to cover]

#### [ ] Step 2: [Step Name]
- **Files:** `path/to/other.py`
- **Action:** [Concise technical logic to implement]
- **Tests:** `path/to/test_other.py` — [Specific scenario to cover]

### Group 2 (depends on: Group 1)
<!-- [What this group accomplishes] -->

#### [ ] Step 3: [Step Name]
- **Files:** `path/to/wiring.py`
- **Action:** [Concise technical logic to implement]
- **Tests:** `path/to/test_wiring.py` — [Specific scenario to cover]

## Constraints & Architecture
- [Hard constraints from the approved SPEC]
- [Relevant architectural invariants or ADR references]
- [Security rules, migration notes, compatibility requirements]

## Verification
- [ ] [Manual test step 1]
- [ ] [Manual test step 2]
