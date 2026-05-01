# Spec: Additional Behavioral Fixtures

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.26 — Additional Behavioral Fixtures
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`
- **Harness Roadmap Marker:** E.26 — Additional Behavioral Fixtures

## Summary
The current behavioral harness protects a small set of high-risk aggregation and reconciliation rules. This feature expands the fixture set to cover the next tier of financial flows after the coverage index exists.

## Problem
- Current fixtures protect transaction aggregation, category snapshots, and recent edit/undo reconciliation.
- Other high-risk financial flows still rely on pytest only and are not represented in the pre-pytest harness.
- Adding new fixtures before the coverage index would make ownership and evidence harder to audit.

## Goals
- Add a small, prioritized set of new behavioral fixtures for high-risk financial flows.
- Use the coverage index metadata for every new fixture.
- Keep fixtures deterministic, in-memory, and independent of external services.
- Preserve fast execution before pytest in Railway builds.

## Non-Goals
- Mirror the full pytest suite in the harness.
- Add broad integration tests, network calls, database calls, or YNAB API calls.
- Cover low-risk formatting or presentation-only behavior.
- Refactor production code unless a fixture exposes a real defect.

## Users / Consumers
- Maintainers reviewing financial safety before deploys.
- AI agents making changes to expense creation, shared expenses, summaries, or account/budget queries.
- Railway deploy builds enforcing high-risk behavioral invariants.

## Expected Behavior
- New fixtures execute through `scripts/harness/check_behavioral_invariants.py`.
- Each new fixture has manifest metadata, owner path, protected rule, pytest evidence, and doc/ADR evidence.
- Fixture failures block `scripts/harness/verify.py --ci`.
- The harness remains quick and does not require service credentials.

## Inputs and Outputs
- **Inputs:** In-memory test data for selected financial flows, manifest metadata, source modules.
- **Outputs:** Behavioral invariant findings in text or JSON.
- **Public Interfaces:** Existing behavioral harness commands only.

## Business Rules and Constraints
- Candidate fixture areas should be selected from high-risk financial behavior, such as shared-expense transaction construction, prepared expense commit invariants, account balance source selection, and summary period aggregation.
- Every new fixture must map to the financial read matrix or a documented ADR.
- Fixtures must use explicit assertion mappings, not dynamic code loading from manifest strings.
- If an app import would require external services, the fixture must use lower-level pure functions or fake repositories instead.

## Edge Cases and Failure Handling
- If a candidate flow cannot be exercised without external services, it should be deferred or split into a smaller pure invariant.
- If a fixture exposes current product drift, implementation must stop and treat that as a bugfix with its own SPEC/PLAN if the fix is not trivial.
- New fixtures must not make local diagnostics noisy or slow.

## Acceptance Criteria
- [x] At least two new high-risk financial behavioral fixtures are added.
- [x] Every new fixture is represented in the manifest coverage index.
- [x] Focused tests prove new fixtures pass and fail in expected ways.
- [x] Direct behavioral diagnostics, CI harness, harness tests, and full pytest pass.

## Open Questions
- Which exact candidate fixtures should be implemented first after E.25: shared-expense construction, prepared expense commit, account balance reads, or summary period aggregation?

## References
- `scripts/harness/behavioral_invariants.toml`
- `src/application/services/expense_service.py`
- `src/application/services/budget_query_service.py`
- `src/application/services/on_demand_summary_service.py`
- `src/domain/services/spending_aggregation.py`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
