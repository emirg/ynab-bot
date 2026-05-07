# Spec: Behavioral Invariant Fixtures

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.23 — Behavioral Invariant Fixtures
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`
- **Harness Roadmap Marker:** E.23 — Behavioral Invariant Fixtures

## Summary
The financial invariant harness currently verifies that documentation, source files, and tests mention critical financial rules. This feature adds executable fixtures for the highest-risk financial behaviors so the CI harness proves the rules still hold before pytest runs.

## Problem
- Evidence checks can pass while behavior changes underneath the referenced snippets.
- The most sensitive financial paths are transaction aggregation and live YNAB reconciliation for `/editar` and `/deshacer`.
- Railway should block deploys on deterministic financial behavior drift before the broader test suite runs.

## Goals
- Execute small, dependency-light financial behavior fixtures from the harness.
- Validate split-aware transaction aggregation, net spending, category snapshot filtering, and edit/undo live YNAB reconciliation.
- Expose a direct advisory command for local diagnosis.
- Keep the harness compatible with `scripts/harness/verify.py --ci`.

## Non-Goals
- Replace pytest or duplicate the full domain/application test suite.
- Add OpenSpec, OpenSDD, OpenSPDD, or external dependencies.
- Call YNAB, Telegram, OpenAI, databases, or network services.
- Enforce linting, typing, coverage, or all product behavior.

## Users / Consumers
- Maintainers and AI agents running local harness diagnostics.
- Railway deploy builds running `verify.py --ci`.
- Future financial feature work that needs a small set of executable invariants before full pytest.

## Expected Behavior
- The harness runs executable behavior fixtures and reports grouped `PASS`, `WARN`, and `FAIL` findings.
- A direct command, `.venv/bin/python scripts/harness/check_behavioral_invariants.py`, runs only the behavioral fixture diagnostics.
- `scripts/harness/verify.py --ci` fails if any behavioral invariant fixture fails.
- Fixtures use deterministic in-memory data only and do not access external services.

## Inputs and Outputs
- **Inputs:** Repository source files, in-memory transaction/category fixtures, in-memory fake YNAB repository state.
- **Outputs:** Harness findings in text or JSON format.
- **Public Interfaces:** `.venv/bin/python scripts/harness/check_behavioral_invariants.py`, optional `--root`, `--strict`, and `--json` CLI flags.

## Business Rules and Constraints
- Spending aggregation must expand split subtransactions and include negative legs from zero-sum shared transactions.
- Net spending must reduce month totals for categorized inflows while excluding `Inflow: Ready to Assign`.
- Budget health fixtures must preserve YNAB category `balance` and filter hidden, deleted, and inactive categories.
- `/editar` must use the live YNAB transaction identity when the transaction still exists, even if local recent fields drift.
- `/deshacer` must use the live YNAB transaction identity when the transaction still exists, while still blocking missing live transactions before deletion.
- Harness code must use only the Python standard library.

## Edge Cases and Failure Handling
- Missing importable source modules produce `FAIL` findings with the failing fixture label.
- Assertion failures produce `FAIL` findings without stack traces in normal text output.
- JSON output remains machine-readable for diagnostics.
- The direct advisory command exits zero by default and nonzero only with `--strict`.

## Acceptance Criteria
- [x] Behavioral fixtures run from a repo-local standard-library harness module.
- [x] `verify.py --ci` blocks on behavioral invariant failures.
- [x] A direct advisory command is registered and documented.
- [x] Focused pytest coverage proves passing and failing behavioral fixtures are reported correctly.
- [x] Repo-level harness and full pytest verification pass.

## Open Questions
- None.

## References
- `docs/wip_state.md`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
- `scripts/harness/checks.py`
- `src/domain/services/spending_aggregation.py`
- `src/application/services/expense_service.py`
