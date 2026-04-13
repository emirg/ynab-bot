# Plan: Financial Advisor Phase 4 Insights

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-04-12-financial-advisor-phase4-insights.md`
- **Goal:** Extend the authenticated advisor dashboard with deterministic, read-only financial insights built from the user's real YNAB data.
- **Approach:** Add an advisor insights read model and rule evaluation layer on top of the existing dashboard aggregation, expose the resulting insights through the advisor dashboard payload, and render them in the current server-served advisor page without changing the auth/session baseline.

## Affected Components
- `src/domain/models/advisor_dashboard.py` — extend the advisor dashboard payload with typed insight objects and any supporting enums/flags
- `src/application/services/advisor_dashboard_service.py` — derive deterministic insight data from existing dashboard context and month-specific budget/category data
- `src/presentation/http/handlers/advisor_api_handler.py` — include insights in the authenticated advisor dashboard response while preserving existing empty/auth behavior
- `src/presentation/http/handlers/advisor_page_handler.py` — render Spanish insight cards/sections in the current advisor HTML/JS flow
- `src/infrastructure/container.py` — only if wiring changes are required for any extracted insight helper/service
- `tests/test_advisor_dashboard_service.py` — cover insight generation rules and low-data behavior
- `tests/test_advisor_http.py`, `tests/test_http_server.py` — cover advisor dashboard payload shape and route behavior
- `tests/test_container.py` — only if DI wiring changes
- `docs/ARCHITECTURE.md`, `docs/wip_state.md`, this plan file — record the new advisor baseline and next handoff

## Prerequisites (Manual)
- [ ] None

## Implementation Steps
### Group 1
#### [x] Step 1: Define the deterministic insight contract in the advisor dashboard domain model
- **Files:** `src/domain/models/advisor_dashboard.py`
- **Action:** Add typed advisor insight structures to the dashboard read model so the API can return stable, explicit insight payloads. Include fields for an insight code, title, explanation, severity or emphasis, and numeric evidence payload. Keep the model additive so the existing summary/trend/category/budget payload remains backward compatible for the Phase 3 UI.
- **Tests:** `tests/test_advisor_dashboard_service.py` — assert serialized dashboard payloads include the new `insights` field and preserve the existing shape for non-insight data.

### Group 2 (depends on: Group 1)
#### [x] Step 2: Implement deterministic insight generation inside the advisor dashboard aggregation flow
- **Files:** `src/application/services/advisor_dashboard_service.py`, `src/domain/models/advisor_dashboard.py`
- **Action:** Build the initial insight set from existing advisor inputs. Start with conservative rules that do not require user-managed configuration:
  - projected overspend or high monthly pace based on current spend versus elapsed month
  - overspent or near-limit budget categories using current monthly budget/activity data
  - inactive categories with assigned budget but no activity
  - high-concentration spending warnings using top-category share of total spend
  - a Spanish “all clear” insight when there is enough data but no notable issues
  Resolve the spec’s open question by avoiding unsupported deterministic `50/30/20` classification in this phase unless the implementation can do so without hidden inference; if not reliable, omit it deliberately and document that choice in code/tests.
- **Tests:** `tests/test_advisor_dashboard_service.py` — add focused cases for each rule, omitted insights in low-data scenarios, income-only/no-expense periods, and no false positives when evidence is insufficient.

### Group 3 (depends on: Group 2)
#### [x] Step 3: Expose advisor insights through the authenticated dashboard API
- **Files:** `src/presentation/http/handlers/advisor_api_handler.py`, `src/presentation/http/server.py`
- **Action:** Extend `GET /api/v1/advisor/dashboard` to include the new insight payload in successful dashboard responses and keep the existing auth, invalid-period, onboarding-state, and empty-state contracts unchanged. For state payloads that do not build a real dashboard, return an empty `insights` collection rather than a partial or guessed response.
- **Tests:** `tests/test_advisor_http.py`, `tests/test_http_server.py` — cover successful responses with insights, onboarding/empty states returning `insights: []`, and unchanged auth/method enforcement.

### Group 4 (depends on: Group 3)
#### [x] Step 4: Render advisor insights in the current server-served dashboard page
- **Files:** `src/presentation/http/handlers/advisor_page_handler.py`
- **Action:** Add an insights section to the existing advisor HTML/JS view and render the API-provided Spanish insight cards without introducing a frontend framework or changing the existing dashboard interaction model. Keep the UI additive, month-first, mobile-safe, and consistent with the current visual language.
- **Tests:** `tests/test_advisor_http.py` — extend advisor page tests to verify the page includes the insight container and still preserves logout/auth behavior.

### Group 5 (depends on: Group 4)
#### [x] Step 5: Update documentation, architecture notes, and handoff state
- **Files:** `docs/ARCHITECTURE.md`, `docs/wip_state.md`, this plan file
- **Action:** Record the Phase 4 insights baseline in architecture docs, mark completed plan steps, and update handoff state with the next recommended advisor slice after deterministic insights land.
- **Tests:** N/A

## Constraints & Architecture
- Keep the current single-repo, single-server advisor baseline from `docs/adrs/2026-04-12-financial-advisor-architecture-baseline.md`.
- Preserve the existing Telegram-issued launch flow and HTTP-only advisor session model from `docs/adrs/2026-04-12-financial-advisor-session-auth.md`.
- Keep all advisor user-facing strings in Spanish.
- Maintain strict per-user isolation for all advisor data and preserve YNAB milliunit invariants.
- Phase 4 must remain deterministic and read-only: no LLM-generated guidance, no Telegram advisor commands, no write actions.
- Prefer omitting weak insights over emitting unsupported or opaque financial advice.
- Avoid introducing a frontend framework, build pipeline, monorepo split, or separate advisor service.

## Verification
- [x] `.venv/bin/pytest tests/test_advisor_dashboard_service.py tests/test_advisor_http.py tests/test_http_server.py tests/test_advisor_page_handler.py tests/test_container.py`
- [x] Manual advisor smoke test through `/analisis` verifying insight cards for a configured user and onboarding/empty states for incomplete setups
