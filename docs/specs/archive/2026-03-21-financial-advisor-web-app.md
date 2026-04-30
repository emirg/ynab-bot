# Spec: YNAB Financial Advisor Web App

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.6
- **Owner:** Codex
- **Related Roadmap Item:** Future Financial Advisor milestone
- **Related ADRs:** `docs/adrs/2026-04-11-sqlite-per-thread-connections.md`, `docs/adrs/2026-04-11-prepared-expense-domain-contract.md`, `docs/adrs/2026-04-12-financial-advisor-persistence-strategy.md`

## Summary
The Financial Advisor is a new analysis experience built on top of the bot's existing YNAB-connected user data. The Telegram bot remains the fastest way to capture expenses, while the advisor becomes the place where users review spending, trends, rules, and recommendations through a richer web-first interface.

This spec defines the expected product behavior and system constraints. It does not lock the final package layout, deployment topology, or persistence implementation details; those belong in the implementation plan and any required ADRs.

## Problem
- The current product is optimized for expense capture and lightweight summaries inside Telegram, but it is not a good surface for richer financial analysis.
- The project now has multiple consumption surfaces: Telegram, a production HTTP API, a local HTTP-first dev harness, and the future advisor experience. The older documentation mixed product requirements with assumptions about monorepo structure, deployment, and persistence changes.
- Without a clean feature spec, implementation work risks making architectural decisions mid-flight and drifting away from the current repo reality.

## Goals
- Provide a dedicated financial analysis experience that is separate from day-to-day expense capture in Telegram.
- Let authenticated users review spending trends, budget-vs-actual views, financial rules, and advisor-style recommendations using the same underlying YNAB-backed data.
- Make access to the advisor start from the bot so the current user identity and YNAB connection remain the source of truth.
- Support phased delivery so foundations, authentication, dashboards, and AI advisor capabilities can ship incrementally.

## Non-Goals
- Replacing Telegram as the primary capture interface for expenses.
- Defining the final repository split, package structure, or deployment topology in this document.
- Requiring a separate public service in the first delivery if the existing single-process HTTP surface can host advisor-related flows during transition.
- Defining the detailed persistence migration strategy here.

## Users / Consumers
- Existing bot users who already connect their own YNAB accounts and want deeper analysis than Telegram can present well.
- Future HTTP or web clients that need advisor-ready read models and authenticated access to the user's financial context.
- Maintainers and AI agents who need a stable description of the feature intent before planning implementation.

## Expected Behavior
- A user can initiate advisor access from Telegram through a dedicated command such as `/analisis`.
- The advisor experience is read-oriented: it helps users inspect and understand their finances, not replace the bot's existing transaction-entry workflow.
- After authentication, the user can access:
  - an executive overview of current spending
  - richer visual analysis by category and period
  - rule-based views such as 50/30/20-style distribution checks
  - conversational advisor guidance backed by the user's financial context
- The advisor experience must use the same per-user identity and YNAB connection model already used by the bot.
- The existing bot behavior, current OAuth flow, and current authenticated HTTP expense endpoint must remain functional while the advisor capability is added.
- Delivery may happen in phases:
  - foundations that make future advisor work safe
  - authentication and user entrypoint from Telegram
  - visual dashboard and analysis views
  - conversational AI advisor features

## Inputs and Outputs
- **Inputs:** Telegram command to open the advisor, authenticated HTTP requests, existing user configuration, YNAB-backed financial data, future web UI interactions, local `http-dev` verification flows, and advisor chat prompts.
- **Outputs:** Authenticated advisor session, visual summaries and charts, financial metrics, advisor responses, and any supporting read-only API responses needed by the UI.
- **Public Interfaces:** Telegram advisor entry command, the current public HTTP server on Railway, future advisor routes/pages, and any supporting internal API contracts used by the web experience.

## Business Rules and Constraints
- The bot remains the authoritative capture interface for expense logging.
- User isolation is mandatory: every advisor view, metric, and recommendation must be scoped to the authenticated user only.
- User-facing copy remains in Spanish.
- YNAB domain invariants remain unchanged, including milliunit handling and per-user repository resolution.
- The advisor flow must reuse the current authentication model rooted in the bot and the user's existing YNAB connection.
- Advisor additions must preserve the current authenticated HTTP expense surface and its security guarantees while new web-facing routes are introduced incrementally.
- Any persistence, packaging, or deployment decision that materially changes current architecture must be recorded in an ADR before or during implementation.
- The current public HTTP surface already exists and cannot be ignored in planning future advisor work.

## Edge Cases and Failure Handling
- If a user has not completed bot onboarding or has not connected YNAB, advisor access must fail gracefully and tell the user what prerequisite is missing.
- If advisor authentication expires or is invalid, the user must be able to restart the flow from Telegram without corrupting their existing bot session.
- If no meaningful financial data is available yet, the advisor should present an empty-state experience instead of misleading analysis.
- If one advisor view or metric cannot be computed, the failure must not expose another user's data or break unrelated bot behavior.
- If deployment remains single-process during early phases, advisor additions must not break existing health checks, OAuth callback handling, or the current HTTP expense endpoint.

## Acceptance Criteria
- [x] The project has a dedicated advisor spec that cleanly separates product behavior from implementation sequencing.
- [x] The advisor is defined as a web-first analysis experience that complements, rather than replaces, Telegram expense capture.
- [x] The spec preserves current invariants: per-user isolation, Spanish UI, YNAB-backed identity, and bot-first entry into advisor access.
- [x] The spec explicitly recognizes phased delivery and the existence of the current public HTTP server.
- [x] The spec does not hard-code a repo split, service topology, or persistence migration strategy that belongs in a plan or ADR.

## Open Questions
- Whether the final advisor architecture should stay on the current public HTTP server during early rollout or move to dedicated API/web services later.

## References
- `docs/plans/archive/2026-03-21-phase1-foundations.md`
- `docs/specs/archive/2026-04-11-http-expense-endpoint-design.md`
- `docs/specs/archive/2026-04-11-shared-http-request-validation.md`
- `docs/specs/archive/2026-04-11-constant-time-http-auth.md`
- `docs/specs/archive/2026-04-11-typed-prepared-expense-flow.md`
- `docs/plans/archive/2026-03-20-financial-advisor-design.md`
- `docs/adrs/2026-04-11-sqlite-per-thread-connections.md`
- `docs/adrs/2026-04-11-prepared-expense-domain-contract.md`
- `docs/adrs/2026-04-12-financial-advisor-persistence-strategy.md`
- `docs/ARCHITECTURE.md`
