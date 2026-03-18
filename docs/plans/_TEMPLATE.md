# Plan: [Feature/Refactor Name]

## Objective & Context
- **Status:** [Draft / In Progress / Completed]
- **Goal:** [1-2 sentences: What are we building/refactoring]
- **Why:** [Core problem being solved]

## Affected Components
<!-- Every file that will be created or modified, for quick impact assessment -->
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
- [Security rules, specific validations, or hard dependencies]
- [Do not repeat ARCHITECTURE.md, only reference it or add feature-specific deviations]

## Verification
- [ ] [Manual test step 1]
- [ ] [Manual test step 2]