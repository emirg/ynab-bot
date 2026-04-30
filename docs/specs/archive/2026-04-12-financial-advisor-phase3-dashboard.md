# Spec: Financial Advisor Phase 3 Dashboard

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.12
- **Owner:** Codex
- **Related Roadmap Item:** Future Financial Advisor milestone
- **Related Spec:** `docs/specs/archive/2026-03-21-financial-advisor-web-app.md`
- **Related ADRs:** `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`, `docs/adrs/2026-04-12-financial-advisor-session-auth.md`

## Summary
Phase 3 turns the advisor from an authenticated placeholder into the first useful read-only analysis surface. It keeps the current Telegram-issued advisor access flow and the current single-server runtime, but replaces the landing page with a real dashboard.

The first dashboard defaults to the current month and emphasizes overview metrics plus spending trends, with category breakdowns visible on the same screen. The implementation must remain additive and avoid monorepo, service-split, or frontend framework work in this phase.

## Problem
- Phase 2 created a safe advisor entrypoint and session model, but the advisor still stops at a placeholder page with no financial insight.
- Existing summary logic is available in the codebase, but it is not exposed through an advisor-specific read model or API tailored for a browser dashboard.
- The next delivery should make the advisor immediately useful without mixing in architecture refactors or a frontend platform decision.

## Goals
- Deliver the first real advisor dashboard behind the existing `/analisis` flow.
- Show read-only financial insight for the authenticated user with overview metrics, trend data, and category breakdowns.
- Support period switching between day, week, and month while defaulting to the current month.
- Preserve current advisor auth/session behavior, HTTP runtime, and per-user isolation guarantees.

## Non-Goals
- Introducing a monorepo split, package extraction, or separate advisor frontend service.
- Adopting a frontend framework or JS build pipeline.
- Adding write actions, editing flows, or conversational advisor features.
- Persisting dashboard caches or advisor read models in the database.

## Users / Consumers
- Existing YNAB bot users who open the advisor through Telegram and want richer financial visibility than Telegram can provide.
- Future advisor UI iterations that can reuse the stable dashboard API contract.

## Expected Behavior
- An authenticated advisor user who opens `/advisor` sees a dashboard instead of a placeholder.
- On initial load, the dashboard requests bootstrap data and then loads dashboard data for the current month.
- The dashboard shows:
  - summary metrics for the selected period
  - a trend view for spending over that period
  - top category breakdowns for the same period
  - budget status context when the selected period is the current month
- The user can switch between `Mes`, `Semana`, and `Día` without leaving the page.
- If the user is missing YNAB connection, budget selection, or default account, the advisor shows a Spanish onboarding state instead of misleading metrics.
- If the user is configured but has no meaningful data, the advisor shows a Spanish empty state rather than pretending analysis is available.
- Logout keeps working exactly as in Phase 2.

## Inputs and Outputs
- **Inputs:** Advisor session cookie, authenticated advisor page load, `period` query parameter (`dia`, `semana`, `mes`), existing user configuration, YNAB transactions, YNAB categories.
- **Outputs:** Advisor dashboard HTML, advisor dashboard JSON payload, period-specific metrics/trends/categories, Spanish onboarding or empty-state messaging.
- **Public Interfaces:** `GET /advisor`, `GET /api/v1/advisor/bootstrap`, `GET /api/v1/advisor/dashboard?period=dia|semana|mes`, `POST /api/v1/advisor/logout`.

## Business Rules and Constraints
- Access still starts from Telegram and uses the existing advisor session cookie model.
- All dashboard data must be scoped strictly to the authenticated user.
- All user-facing advisor copy remains in Spanish.
- YNAB milliunit rules remain unchanged.
- The first screen defaults to the current month.
- The dashboard emphasizes overview plus trends first; budget-vs-actual is secondary month-only context.
- The implementation remains on the current single-repo, single-server architecture baseline for this phase.

## Edge Cases and Failure Handling
- If the session is missing or expired, advisor API requests fail with the existing advisor auth error contract.
- If the requested period is invalid, the dashboard API returns a 400 error with a clear Spanish message.
- If YNAB data cannot be fetched for a valid session, the dashboard must fail without leaking another user's data or breaking unrelated advisor routes.
- If the user has income-only activity or no expense activity in the selected period, the dashboard should show zero/empty data states consistently.
- If monthly budget data is unavailable or the selected period is not monthly, budget status should be omitted rather than guessed.

## Acceptance Criteria
- [x] `GET /api/v1/advisor/dashboard?period=dia|semana|mes` exists and is protected by the existing advisor session.
- [x] The advisor page renders a month-first dashboard with overview metrics, trends, and category breakdowns.
- [x] Period switching between month, week, and day updates the displayed advisor data.
- [x] Advisor onboarding and empty states are rendered in Spanish and reflect the authenticated user's real status.
- [x] Existing advisor bootstrap/logout behavior and the existing expense API remain unchanged.
- [x] No monorepo refactor, service split, or frontend framework is introduced in this phase.

## Open Questions
- None

## References
- `docs/specs/archive/2026-03-21-financial-advisor-web-app.md`
- `docs/specs/archive/2026-04-12-financial-advisor-phase2-access-auth.md`
- `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`
- `docs/adrs/2026-04-12-financial-advisor-session-auth.md`
