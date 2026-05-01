# Spec: Handoff Resume Prompt

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.28 — Handoff Resume Prompt
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`
- **Harness Roadmap Marker:** E.28 — Handoff Resume Prompt

## Summary
Cross-agent continuity improves when the next AI worker receives a task-specific prompt, not only a state summary. This feature adds a required `Resume Prompt` field to `docs/wip_state.md` and updates workflow documentation so future handoffs preserve it.

## Problem
- `docs/wip_state.md` records objective, last action, modified files, blocker state, and next step, but does not give a ready-to-use prompt for another AI tool.
- A Gemini CLI, Claude Code, or Codex handoff can miss sequencing details such as which draft plan to start, which items to avoid, and which docs to read first.
- The current harness does not enforce the handoff-state structure.

## Goals
- Add a required task-specific `Resume Prompt` field to the handoff protocol.
- Update the current `docs/wip_state.md` with a useful prompt for the planned harness agenda.
- Add harness validation so malformed handoff fields fail before deploy when the session-state file is present.
- Keep the handoff format simple Markdown text that any AI CLI can consume.

## Non-Goals
- Create a separate handoff document.
- Add tool-specific prompt templates for every AI vendor.
- Implement E.25, E.26, or E.27.
- Change the SPEC/PLAN/ADR workflow.

## Users / Consumers
- Future AI workers resuming from `docs/wip_state.md`.
- Maintainers delegating work across Codex, Gemini CLI, Claude Code, or other agents.
- Railway deploy builds that enforce workflow documentation coherence.

## Expected Behavior
- `docs/AI_WORKFLOW.md` lists `Resume Prompt` as part of the required handoff structure.
- `docs/wip_state.md` includes `Resume Prompt:` with concrete next-agent instructions.
- The harness reports `FAIL` if an existing `docs/wip_state.md` is missing required handoff fields.
- Because `docs/wip_state.md` is ignored session state, the harness reports `WARN` when it is absent instead of blocking Railway.
- Existing advisory and CI harness commands continue to work.

## Inputs and Outputs
- **Inputs:** `docs/AI_WORKFLOW.md`, `docs/wip_state.md`.
- **Outputs:** Updated handoff documentation and harness findings.
- **Public Interfaces:** `.venv/bin/python scripts/harness/check_docs.py`, `.venv/bin/python scripts/harness/verify.py --ci`.

## Business Rules and Constraints
- The prompt must be task-specific and overwritten when handoff state changes.
- The prompt must direct the next agent to read `AGENTS.md`, `docs/AI_WORKFLOW.md`, `docs/DOCUMENTATION_WORKFLOW.md`, and `docs/wip_state.md`.
- The prompt must identify the recommended next item without authorizing unrelated planned items.
- Harness validation must use only the Python standard library.

## Edge Cases and Failure Handling
- A missing `docs/wip_state.md` warns because the file is ignored local session state.
- A missing `Resume Prompt:` line fails as malformed handoff state.
- A generic or stale prompt is a review concern, not something the initial harness needs to semantically validate.

## Acceptance Criteria
- [x] `docs/AI_WORKFLOW.md` requires `Resume Prompt`.
- [x] `docs/wip_state.md` includes a concrete current resume prompt.
- [x] Harness tests cover missing required handoff fields.
- [x] Documentation harness and focused harness tests pass.

## Open Questions
- None.

## References
- `docs/AI_WORKFLOW.md`
- `docs/wip_state.md`
- `scripts/harness/checks.py`
- `tests/harness/test_checks.py`
