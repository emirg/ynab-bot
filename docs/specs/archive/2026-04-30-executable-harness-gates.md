# Spec: Executable Harness Gates

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.11
- **Owner:** Codex
- **Related Roadmap Item:** Documentation workflow enforcement baseline
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`

## Summary
The repository needs an executable baseline that checks whether the AI documentation workflow is internally coherent before deploy builds run tests. This feature adds standard-library-only harness commands for local diagnostics and Railway blocking verification, focused on documentation workflow state and stale agent references.

## Problem
- The project depends on `SPEC -> PLAN -> IMPLEMENT -> REVIEW -> DONE`, but today that state is only prose and can drift.
- Active completed documents, stale legacy workflow references, and outdated agent context can mislead future workers before tests even run.
- Railway currently runs `pytest` directly, so documentation workflow failures do not block deploy builds.

## Goals
- Provide a local advisory command for documentation workflow diagnostics.
- Provide a CI command that fails on workflow violations before pytest runs in Railway builds.
- Detect missing workflow docs/templates, invalid active SPEC/PLAN metadata, broken ADR doc references, stale orchestration references, and agent entrypoint drift.
- Clean current documentation drift so the checked-in repository passes the new gate.

## Non-Goals
- Add OpenSpec, OpenSDD, or another external specification framework.
- Add linting, type checking, coverage thresholds, or runtime financial checks to the first gate.
- Run pytest inside the harness verifier.

## Users / Consumers
- AI assistants following this repository's documentation workflow.
- Maintainers reviewing documentation state before shipping changes.
- Railway deploy builds that need an early, deterministic failure signal.

## Expected Behavior
- `.venv/bin/python scripts/harness/check_docs.py` prints grouped PASS, WARN, and FAIL findings for the repository and exits zero by default.
- `.venv/bin/python scripts/harness/verify.py --ci` runs the same documentation checks in blocking mode and exits nonzero on failures.
- Railway build verification runs the harness CI command before pytest.
- Current repository documentation and agent entrypoints pass the harness after cleanup.

## Inputs and Outputs
- **Inputs:** Markdown files under `docs/`, root agent entrypoints, `.claude/agents/`, and `railway.toml`.
- **Outputs:** Human-readable grouped diagnostics and process exit codes.
- **Public Interfaces:** `scripts/harness/check_docs.py`, `scripts/harness/verify.py --ci`.

## Business Rules and Constraints
- The harness must use only the Python standard library.
- The first blocking gate covers documentation workflow coherence only.
- Required workflow docs and templates must exist.
- Active SPECs must have valid metadata and may not be `Implemented` or `Completed`.
- Active PLANs must have valid metadata, reference an existing source SPEC, and may not be `Completed` or `Implemented`.
- ADR references to SPECs and PLANs must point to existing files, including archived paths.
- Agent entrypoints must reference both `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.
- Any stale legacy orchestration workflow path reference is a CI failure.

## Edge Cases and Failure Handling
- Missing metadata should produce a clear FAIL pointing to the document.
- Broken ADR references should identify both the ADR and missing target path.
- Local advisory mode should still exit zero when failures exist, unless strict mode is requested.
- CI mode should exit nonzero when any FAIL finding exists.

## Acceptance Criteria
- [x] Required docs/templates are verified by automated tests.
- [x] Active SPEC and PLAN metadata and source-spec link rules are covered by tests.
- [x] ADR reference validation supports archive paths and fails broken references.
- [x] Agent entrypoint and stale orchestration reference checks are covered.
- [x] Current checked-in repository passes `.venv/bin/python scripts/harness/verify.py --ci`.
- [x] Railway build command runs `python scripts/harness/verify.py --ci && pytest`.

## Open Questions
- None.

## References
- `docs/DOCUMENTATION_WORKFLOW.md`
- `docs/AI_WORKFLOW.md`
- `railway.toml`
