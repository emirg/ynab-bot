# Spec: Financial Advisor Phase 4 Insights

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** Future Financial Advisor milestone
- **Related Spec:** `docs/specs/archive/2026-03-21-financial-advisor-web-app.md`
- **Related ADRs:** `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`, `docs/adrs/2026-04-12-financial-advisor-session-auth.md`

## Summary
Phase 4 adds deterministic financial insights to the authenticated advisor dashboard. It builds on the completed Phase 3 dashboard baseline and introduces rule-based interpretation of the user's real YNAB data without adding any conversational or LLM-generated advisor behavior.

The advisor remains web-first, read-only, and rooted in the existing Telegram-issued session flow. Users should see clear Spanish insight cards or sections that explain notable conditions such as spending distribution concerns, projected overspending, and budget hygiene findings.

## Problem
- Phase 3 delivers metrics, trends, and category breakdowns, but it still leaves most interpretation work to the user.
- The advisor product goal includes guidance and recommendations, but the next step should stay deterministic and testable before introducing any conversational layer.
- Without a bounded insights phase, future advisor work risks mixing rule logic, UI changes, and LLM behavior in a single delivery.

## Goals
- Add a deterministic insights layer to the existing advisor dashboard.
- Surface notable financial conditions using rule-based logic derived from real user data.
- Keep all insights scoped to the authenticated user and presented in Spanish.
- Preserve the current advisor access model, dashboard baseline, and read-only behavior.

## Non-Goals
- Adding conversational or LLM-generated advisor guidance.
- Introducing Telegram advisor commands or duplicating advisor insights in the bot UI.
- Adding user-configurable rule definitions or category classification management.
- Adding write actions, budget edits, or transaction edits from the advisor.
- Introducing a frontend framework, service split, or separate advisor runtime.

## Users / Consumers
- Existing advisor users who already access `/advisor` through Telegram and want actionable interpretation, not only raw metrics.
- Future advisor phases that can build on a stable deterministic insights contract before adding more advanced guidance.

## Expected Behavior
- An authenticated advisor user who opens `/advisor` continues to see the existing month-first dashboard, now extended with an insights area.
- The advisor computes insights from the authenticated user's real YNAB-backed dashboard context for the selected period, with month-first emphasis.
- The initial insight set should cover:
  - spending distribution checks against a fixed guidance heuristic such as `50/30/20`
  - categories with unusually high budget execution or projected overspend
  - month projection warnings when current spending pace suggests an unfavorable end-of-month outcome
  - inactive categories that still have assigned budget but no activity
  - a Spanish "all clear" style state when no notable issues are detected
- Every insight should include a short Spanish explanation and the numeric evidence needed to justify it.
- If a specific insight cannot be computed reliably from the available data, that insight is omitted rather than guessed.
- Insight presentation remains read-only and must not interfere with logout, bootstrap, or the existing dashboard behavior.

## Inputs and Outputs
- **Inputs:** Advisor session cookie, authenticated advisor page load, selected dashboard period, existing advisor dashboard metrics, YNAB transaction data, YNAB category/budget data.
- **Outputs:** Advisor insight payloads and dashboard UI sections/cards containing Spanish rule-based interpretations and supporting numeric evidence.
- **Public Interfaces:** `GET /advisor`, `GET /api/v1/advisor/dashboard?period=dia|semana|mes`, and any additive advisor insight fields or companion advisor insight endpoint defined by the implementation plan.

## Business Rules and Constraints
- All insight data must be scoped strictly to the authenticated user.
- All user-facing advisor copy remains in Spanish.
- YNAB milliunit rules remain unchanged.
- Phase 4 must remain deterministic: no LLM-generated interpretations, summaries, or classifications.
- The advisor remains web-first and read-only in this phase.
- The existing Telegram-issued launch flow, HTTP-only advisor session cookie, and current single-server advisor baseline remain unchanged.
- The first delivery should prefer fixed, explainable heuristics over configurable or opaque rules.
- Insights should be conservative: if the system lacks enough evidence for a reliable conclusion, it should omit the insight rather than infer aggressively.

## Edge Cases and Failure Handling
- If the session is missing or expired, advisor insight access fails through the existing advisor auth contract.
- If the selected period is valid but does not support a given insight reliably, the response omits that insight and keeps the rest of the dashboard usable.
- If the user has no meaningful expense data, the advisor should show a Spanish empty or low-data state instead of fabricating recommendations.
- If the user has income-only activity, the advisor should not pretend spending-rule analysis is meaningful.
- If category classification needed for a heuristic cannot be derived confidently from the chosen deterministic rules, the system should skip that heuristic or degrade to a partial insight instead of introducing hidden AI behavior.
- If YNAB data fetches fail for a valid session, the feature must fail without leaking another user's data or breaking unrelated advisor routes.

## Acceptance Criteria
- [x] The authenticated advisor dashboard exposes deterministic insight output in addition to Phase 3 metrics.
- [x] Users see Spanish insights for notable cases such as spending distribution concerns, projection warnings, and inactive budget categories when relevant.
- [x] When no notable conditions are detected, the advisor shows a Spanish no-issues or low-signal state instead of empty unexplained space.
- [x] Insight generation remains read-only, per-user isolated, and free of LLM-generated content.
- [x] Existing advisor auth, bootstrap, logout, and dashboard period switching continue to work.
- [x] The implementation does not introduce Telegram advisor flows, configurable rule management, or architecture changes outside the current advisor baseline.

## Open Questions
- Phase 4 intentionally does not implement deterministic `50/30/20` classification because there is no defensible non-configurable category mapping in the current product model. A future phase can revisit this with explicit user-managed grouping or a separately approved heuristic.

## References
- `docs/specs/archive/2026-03-21-financial-advisor-web-app.md`
- `docs/specs/archive/2026-04-12-financial-advisor-phase3-dashboard.md`
- `docs/plans/archive/2026-04-12-financial-advisor-phase3-dashboard.md`
- `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`
- `docs/adrs/2026-04-12-financial-advisor-session-auth.md`
- `docs/ARCHITECTURE.md`
