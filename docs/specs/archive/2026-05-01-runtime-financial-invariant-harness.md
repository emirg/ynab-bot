# Spec: Runtime Financial Invariant Harness

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.22
- **Harness Roadmap Marker:** E.22
- **Related ADRs:** `docs/adrs/2026-05-01-spec-framework-evaluation.md`

## Summary
Add the first financial-safety layer to the executable harness. The harness should verify that the repository still documents, tests, and structurally protects the core YNAB source-of-truth invariants before Railway deploy tests run.

This slice borrows lightweight SPDD-style safeguards from the framework evaluation without adopting OpenSPDD or adding generated prompt artifacts.

## Problem
- The current harness protects documentation lifecycle, command drift, roadmap coherence, and Railway configuration.
- It does not yet protect the product's highest-risk assumptions: milliunit handling, YNAB source-of-truth boundaries, and the financial read matrix.
- These assumptions are easy to regress when future features reuse convenient local state or aggregate the wrong YNAB surface.

## Goals
- Add executable harness checks for the financial invariants already established in workflow docs and ADRs.
- Require source and test evidence that financial reports use the right YNAB source for each value type.
- Keep the checks deterministic, local, and standard-library-only.
- Wire the checks into the existing advisory and CI harness path.

## Non-Goals
- Do not execute live YNAB API calls.
- Do not add a new OpenSPDD dependency or generated prompt framework.
- Do not replace existing unit or integration tests.
- Do not enforce broad lint, type, or coverage thresholds in this slice.

## Users / Consumers
- Maintainers extending financial reporting, advisor, summary, edit, or undo flows.
- AI agents implementing future changes under `docs/AI_WORKFLOW.md`.
- Railway deploy builds that rely on `scripts/harness/verify.py --ci`.

## Expected Behavior
- The harness emits grouped PASS/FAIL findings for financial invariant evidence.
- CI mode fails if required source/test evidence disappears.
- Advisory mode reports the same findings without forcing a nonzero exit unless strict mode is used.
- The repository passes the new financial invariant gate after this slice lands.

## Inputs and Outputs
- **Inputs:** repository source files, test files, workflow docs, ADRs, and harness command-line invocations.
- **Outputs:** harness findings in text and JSON output.
- **Public Interfaces:** `.venv/bin/python scripts/harness/check_financial_invariants.py`, `.venv/bin/python scripts/harness/check_docs.py`, `.venv/bin/python scripts/harness/verify.py --ci`.

## Business Rules and Constraints
- YNAB amounts are milliunits internally and expenses are negative when sent to YNAB.
- Spending totals and category rankings must come from transaction data, not local recent-action state.
- Budget health and available/overspent state must come from YNAB category snapshots.
- Account balances must come from YNAB account fields.
- `/recent`, `/editar`, and `/deshacer` remain workflow conveniences, not canonical financial reporting.
- Per-user isolation and YNAB source-of-truth rules remain non-negotiable.

## Edge Cases and Failure Handling
- If a required evidence file is missing, report a targeted FAIL with the expected invariant.
- If source evidence exists but test evidence disappears, fail with a test-specific message.
- If future refactors move implementation files, maintainers should update the harness evidence map in the same change.

## Acceptance Criteria
- [x] Harness checks cover milliunits, spending totals, budget health, account balances, and recent/edit/undo convenience boundaries.
- [x] A direct advisory financial invariant command is available for local diagnostics.
- [x] `verify.py --ci` includes the financial invariant checks and blocks on violations.
- [x] Focused pytest coverage proves the new checks fail for missing evidence and pass for a valid fixture repo.
- [x] Checked-in repository documentation and tests pass the updated harness.

## Open Questions
- None.

## References
- `docs/adrs/2026-05-01-spec-framework-evaluation.md`
- `docs/adrs/2026-04-12-ynab-source-of-truth.md`
- `docs/AI_WORKFLOW.md`
