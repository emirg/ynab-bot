# Plan: YNAB Source Of Truth Hardening

## Objective & Context
- **Status:** Draft
- **Source Spec:** `docs/specs/2026-04-12-ynab-source-of-truth-hardening.md`
- **Goal:** Make all financial reads use the correct YNAB-backed source and eliminate remaining drift between bot/advisor outputs and YNAB.
- **Approach:** Introduce a shared source-of-truth policy plus reusable spending aggregation helpers, then align each feature to the proper YNAB data source by value type.

## Affected Components
- `docs/specs/2026-04-12-ynab-source-of-truth-hardening.md` — new cross-cutting product spec
- `docs/plans/2026-04-12-ynab-source-of-truth-hardening.md` — execution plan derived from that spec
- Shared spending aggregation helpers — split-aware transaction expansion and Reflect-compatible spending filters
- Summary and advisor services — `/resumen`, weekly summary, advisor dashboard, advisor insights
- Budget query service and formatter paths — align budget-summary-style spending totals with the shared rule
- Learning and transaction-edit flows — document and tighten non-authoritative recent/edit/undo behavior where needed

## Prerequisites (Manual)
- [ ] None.

## Implementation Steps

### Group 1

#### [ ] Step 1: Add canonical source-of-truth policy
- **Files:** `README.md`, `docs/ARCHITECTURE.md`, `docs/AI_WORKFLOW.md`, `AGENTS.md`, `docs/dev/README.md`
- **Action:** Reference the new source-of-truth matrix directly in the main docs so users, developers, and AI share one rule for financial reads.
- **Tests:** N/A — documentation-only.

#### [ ] Step 2: Introduce shared financial read helpers
- **Files:** shared helper module(s) under `src/domain/services/` or `src/application/services/`
- **Action:** Add reusable helpers for split-aware transaction expansion, Reflect-compatible spending filters, and normalized monthly category snapshot interpretation.
- **Tests:** focused helper tests for split expansion, zero-sum exclusion, and category/group filtering.

### Group 2 (depends on: Group 1)

#### [ ] Step 3: Align spending views to Reflect-compatible transaction logic
- **Files:** on-demand summary and weekly summary models/services, advisor dashboard monthly/period spending logic
- **Action:** Update `/resumen dia`, `/resumen semana`, weekly summary, and monthly spending totals/rankings to use the shared transaction-based spending aggregation that expands splits and excludes non-spending artifacts.
- **Tests:** summary and weekly regression tests for split-heavy categories and monthly spending consistency.

#### [ ] Step 4: Align budget-health views to category snapshot logic
- **Files:** monthly `/resumen` budget logic, advisor budget status, advisor insight generation
- **Action:** Ensure budget health always uses YNAB category snapshot fields, especially `balance` for remaining/overspending and `activity` for monthly category activity.
- **Tests:** carryover-positive category tests, overspending tests, and `/resumen` versus advisor consistency checks.

### Group 3 (depends on: Group 2)

#### [ ] Step 5: Audit and align budget queries
- **Files:** `src/application/services/budget_query_service.py`, related formatter paths, related tests
- **Action:** Keep category/account balance queries directly YNAB-backed and align budget-summary spending totals/top categories with the same Reflect-compatible rule used elsewhere.
- **Tests:** budget summary, category balance, and account balance regressions.

#### [ ] Step 6: Clarify workflow-convenience commands
- **Files:** learning handler/service docs and any relevant service logic for recent/edit/undo validation
- **Action:** Preserve `/recent`, `/editar`, and `/deshacer` as convenience flows, but document their scope clearly and fail safely when local references no longer match live YNAB state.
- **Tests:** recent/edit/undo safety tests when referenced YNAB transactions are missing or stale.

### Group 4 (depends on: Group 3)

#### [ ] Step 7: Add cross-feature regression coverage
- **Files:** summary, advisor, budget query, weekly summary, and spending-helper test suites
- **Action:** Add cross-feature tests that prove the same YNAB-backed rules are used consistently across bot and advisor surfaces.
- **Tests:** end-to-end-style assertions for `/resumen`, weekly summary, advisor dashboard, and budget summary query.

## Constraints & Architecture
- Keep YNAB as the financial source of truth.
- Keep all user-facing strings in Spanish.
- Preserve milliunit invariants.
- Keep per-user isolation and resolve YNAB access via `YNABRepositoryFactory`.
- Fail closed when a feature requires authoritative YNAB data and that data is unavailable.
- Treat `/recent`, `/editar`, and `/deshacer` as workflow conveniences, not canonical financial reporting.

## Verification
- [ ] `/resumen dia` and `/resumen semana` handle split-backed category totals correctly.
- [ ] `/resumen mes` total spent matches the chosen Reflect-compatible monthly spending definition.
- [ ] Advisor monthly totals and top categories match the same monthly spending definition as `/resumen mes`.
- [ ] Budget warnings in `/resumen` and advisor are driven by YNAB category `balance`.
- [ ] Budget summary query uses the same monthly spending semantics as the rest of the app.
- [ ] `/recent`, `/editar`, and `/deshacer` behave safely when local references drift from YNAB.

## Assumptions
- YNAB Reflect-compatible spending is the canonical target for monthly spending totals.
- YNAB category snapshots are canonical for budget-health semantics.
- Fail closed is preferred over labeled stale approximations.
- `/recent`, `/editar`, and `/deshacer` remain workflow conveniences in this slice rather than becoming full YNAB-browsing features.
- No DB schema change is required unless implementation discovers a missing validation field for safe recent/edit/undo reconciliation.
