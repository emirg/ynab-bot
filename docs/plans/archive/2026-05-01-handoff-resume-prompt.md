# Plan: Handoff Resume Prompt

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-handoff-resume-prompt.md`
- **Harness Roadmap Marker:** E.28 — Handoff Resume Prompt
- **Goal:** Add a required resume prompt to handoff state and enforce it through the documentation harness.
- **Approach:** Update the workflow docs and current handoff state, add standard-library harness validation for required handoff fields, cover it with focused tests, then archive this SPEC/PLAN after verification.

## Affected Components
- `docs/AI_WORKFLOW.md` — add `Resume Prompt` to the strict handoff structure.
- `docs/wip_state.md` — add the current task-specific resume prompt.
- `scripts/harness/checks.py` — validate required handoff fields.
- `tests/harness/test_checks.py` — add minimal repo handoff state and missing-field coverage.
- `ROADMAP.md` — add E.28 completion entry.
- `docs/adrs/2026-04-30-executable-harness-gates.md` — record handoff-state validation as part of the harness.

## Prerequisites (Manual)
- [x] User approved adding a next-agent prompt to handoff documentation.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Documentation contract. -->

#### [x] Step 1: Update handoff documentation
- **Files:** `docs/AI_WORKFLOW.md`, `docs/wip_state.md`
- **Action:** Add the required `Resume Prompt` field to the workflow protocol and current handoff state.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`.

### Group 2 (depends on: Group 1)
<!-- Harness enforcement. -->

#### [x] Step 2: Validate handoff fields
- **Files:** `scripts/harness/checks.py`, `tests/harness/test_checks.py`
- **Action:** Add `docs/wip_state.md` field validation, including `Resume Prompt`; missing ignored session state warns instead of blocking clean CI checkouts.
- **Tests:** `.venv/bin/pytest tests/harness -q`.

### Group 3 (depends on: Group 2)
<!-- Close-out. -->

#### [x] Step 3: Close documentation state
- **Files:** `ROADMAP.md`, `docs/adrs/2026-04-30-executable-harness-gates.md`, archived SPEC/PLAN, `docs/wip_state.md`
- **Action:** Mark this slice complete, archive docs, update roadmap/ADR, and refresh handoff state.
- **Tests:** Full verification commands.

## Constraints & Architecture
- Handoff state remains a simple Markdown text file.
- Harness validation stays standard-library only.
- Do not implement E.25, E.26, or E.27 in this slice.
- Keep `Resume Prompt` tool-agnostic enough for Codex, Gemini CLI, Claude Code, or another AI CLI.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
