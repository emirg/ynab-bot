# Spec: Harness Output UX

## Metadata
- **Status:** Approved
- **Owner:** Codex
- **Related Roadmap Item:** E.27 — Harness Output UX
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`

## Summary
The harness now validates documentation lifecycle, command registry, Railway config, financial evidence, behavioral fixtures, and fixture metadata. As coverage grows, local output needs clearer summaries and more actionable failure messages without weakening JSON automation.

## Problem
- Text output is grouped by severity but can become long as more checks are added.
- Failure messages identify the broken condition, but do not always tell the user which command or file to inspect next.
- JSON output is machine-readable but lacks higher-level grouping by check family.

## Goals
- Improve local text output readability for humans.
- Preserve stable JSON output for automation while optionally adding structured grouping fields.
- Make failures more actionable by including check family, remediation hint, or related command where useful.
- Keep advisory commands and CI behavior unchanged.

## Non-Goals
- Build a rich TUI, web UI, or dashboard.
- Change pass/fail semantics for existing checks.
- Remove existing text or JSON fields in a breaking way.
- Introduce non-standard-library formatting dependencies.

## Users / Consumers
- Maintainers running local harness diagnostics.
- AI agents diagnosing harness failures.
- Railway deploy logs where concise failure context matters.

## Expected Behavior
- Text output remains grouped by `PASS`, `WARN`, and `FAIL`, but failures are easier to scan.
- JSON output remains valid and backwards-compatible with existing `summary` and `findings` fields.
- Findings can carry optional check-family or remediation metadata if implementation chooses to extend the data model.
- Direct commands keep their current default exit behavior.

## Inputs and Outputs
- **Inputs:** Existing `Finding` objects and harness result data.
- **Outputs:** Text and JSON diagnostics.
- **Public Interfaces:** `check_docs.py`, `check_financial_invariants.py`, `check_behavioral_invariants.py`, `verify.py --ci`.

## Business Rules and Constraints
- JSON output must continue to include `summary` and `findings`.
- Advisory commands must still exit zero unless `--strict` is used.
- CI command must still exit nonzero on `FAIL`.
- Output improvements must not hide failures or make deploy logs ambiguous.

## Edge Cases and Failure Handling
- Empty groups must still render clearly.
- Long failure lists should remain deterministic and stable.
- Optional metadata must not break consumers that ignore unknown JSON fields.
- If output changes affect tests, tests must assert behavior rather than brittle full snapshots.

## Acceptance Criteria
- [ ] Text output gives clearer high-signal failure context.
- [ ] JSON output remains backwards-compatible.
- [ ] Focused tests cover formatting changes for pass/fail/warn groups.
- [ ] All existing harness commands keep their exit-code contracts.

## Open Questions
- Should the first UX slice add check-family metadata to `Finding`, or only improve text formatting around existing fields?

## References
- `scripts/harness/checks.py`
- `scripts/harness/check_docs.py`
- `scripts/harness/check_financial_invariants.py`
- `scripts/harness/check_behavioral_invariants.py`
- `scripts/harness/verify.py`
- `docs/harness/COMMANDS.md`
