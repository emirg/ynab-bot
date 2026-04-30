# Plan: Harness Command Registry

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-04-30-harness-command-registry.md`
- **Harness Roadmap Marker:** E.20
- **Goal:** Add a canonical command registry and harness checks that keep living command instructions aligned.
- **Approach:** Add failing tests first, introduce a small standard-library registry module, wire checks into `run_checks()`, update living docs, then archive the SPEC/PLAN and update ROADMAP/ADR.

## Affected Components
- `scripts/harness/commands.py` — canonical command definitions.
- `scripts/harness/checks.py` — command registry and living-doc checks.
- `tests/harness/test_checks.py` — fixture tests for missing registry/doc references.
- `docs/harness/COMMANDS.md` — human-readable command registry.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/AI_WORKFLOW.md` — living command references.
- `ROADMAP.md`, `docs/adrs/2026-04-30-executable-harness-gates.md` — closeout documentation.

## Prerequisites (Manual)
- [x] User approved the Harness Command Registry slice.

## Implementation Steps

### Group 1
<!-- Test-first coverage for command drift. -->

#### [x] Step 1: Add failing command registry tests
- **Files:** `tests/harness/test_checks.py`
- **Action:** Add tests for valid command registry docs, missing command registry doc, missing canonical command in registry doc, missing agent command, and missing workflow harness command.
- **Tests:** `tests/harness/test_checks.py` — new tests should fail before implementation.

### Group 2 (depends on: Group 1)
<!-- Implement registry and checks. -->

#### [x] Step 2: Add command registry module and checks
- **Files:** `scripts/harness/commands.py`, `scripts/harness/checks.py`
- **Action:** Move canonical harness/Railway/run/test command constants into the registry, update Railway checks to use them, and add living-doc command validation.
- **Tests:** `tests/harness/test_checks.py`.

### Group 3 (depends on: Group 2)
<!-- Update living docs and close out. -->

#### [x] Step 3: Update command docs and archive feature docs
- **Files:** `docs/harness/COMMANDS.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/AI_WORKFLOW.md`, `ROADMAP.md`, `docs/adrs/2026-04-30-executable-harness-gates.md`, this SPEC/PLAN.
- **Action:** Add canonical command references, add E.20, update ADR references, mark SPEC/PLAN complete, and archive both docs with roadmap markers.
- **Tests:** full harness and pytest verification.

## Constraints & Architecture
- Keep all harness code standard-library only.
- Do not validate archived historical plans for command text.
- Keep existing CLI contracts unchanged.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
