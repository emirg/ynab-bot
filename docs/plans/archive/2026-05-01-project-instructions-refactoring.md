# Plan: Project Instructions Refactoring

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-project-instructions-refactoring.md`
- **Harness Roadmap Marker:** E.29 — Project Instructions Refactoring
- **Goal:** Consolidate shared agent instructions into `AGENTS.md`, reduce Claude/Gemini entrypoints to thin role-mapping wrappers, and enforce the pattern through the documentation harness.
- **Approach:** Add harness tests for the desired wrapper contract first, then refactor the entrypoint docs, implement standard-library checks, update governance docs, and verify the repo.

## Affected Components
- `AGENTS.md` — canonical shared project instructions.
- `CLAUDE.md` — thin Claude Code wrapper with role mapping.
- `GEMINI.md` — thin Gemini CLI wrapper with role mapping.
- `scripts/harness/checks.py` — instruction wrapper drift validation.
- `tests/harness/test_checks.py` — focused fixture coverage for wrapper checks.
- `docs/adrs/2026-04-30-executable-harness-gates.md` — record the instruction-entrypoint enforcement layer.
- `ROADMAP.md` — mark E.29 complete at closeout.
- `docs/wip_state.md` — update local handoff state at closeout.

## Prerequisites (Manual)
- [x] User approves this PLAN for implementation.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Test-first coverage for instruction wrapper drift. -->

#### [x] Step 1: Add harness tests for agent wrapper contract
- **Files:** `tests/harness/test_checks.py`
- **Action:** Add fixture tests that cover a valid `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` layout plus failures for missing `AGENTS.md` references, duplicated shared command blocks, duplicated source-of-truth sections, and missing role mappings.
- **Tests:** `tests/harness/test_checks.py` — new tests should fail before harness implementation.

### Group 2 (depends on: Group 1)
<!-- Implement the harness rule and refactor the docs it protects. -->

#### [x] Step 2: Refactor agent entrypoint docs
- **Files:** `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- **Action:** Move shared instructions into `AGENTS.md`; make Claude/Gemini wrappers point to `AGENTS.md`; retain only the read-first instruction and role mapping in wrappers. Replace copied command blocks with a pointer to `docs/harness/COMMANDS.md`.
- **Tests:** Harness tests from Step 1 plus repo-level documentation harness.

#### [x] Step 3: Add instruction drift checks
- **Files:** `scripts/harness/checks.py`
- **Action:** Extend `check_agent_entrypoints()` or add a focused helper that validates canonical shared content in `AGENTS.md`, required wrapper references to `AGENTS.md`, wrapper role mappings, and prohibited duplicated sections in `CLAUDE.md`/`GEMINI.md`.
- **Tests:** `tests/harness/test_checks.py` — valid and invalid wrapper fixtures.

### Group 3 (depends on: Group 2)
<!-- Close documentation loop. -->

#### [x] Step 4: Update governance docs and closeout state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/specs/2026-05-01-project-instructions-refactoring.md`, `docs/plans/2026-05-01-project-instructions-refactoring.md`, `docs/wip_state.md`
- **Action:** Record the new harness enforcement layer in the ADR, mark E.29 complete in ROADMAP, mark SPEC/PLAN complete, archive SPEC/PLAN, and update handoff state.
- **Tests:** Repo-level harness verification.

## Constraints & Architecture
- Preserve the existing workflow docs as the source for process details.
- Do not remove tool-specific role mappings from Claude or Gemini wrappers.
- Keep harness code standard-library only.
- Use the command registry instead of copying operational command blocks into multiple entrypoints.
- Do not change runtime application behavior.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
