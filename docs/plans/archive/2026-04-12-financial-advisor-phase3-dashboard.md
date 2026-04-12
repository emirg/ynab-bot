# Plan: Financial Advisor Phase 3 Dashboard

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-04-12-financial-advisor-phase3-dashboard.md`
- **Goal:** Deliver the first useful advisor dashboard on top of the completed advisor session/auth baseline.
- **Approach:** Add an advisor-specific dashboard service and API, then replace the placeholder advisor page with a month-first read-only dashboard rendered by the existing server-served HTML/JS flow.

## Affected Components
- `src/domain/models/` and `src/application/services/` — advisor dashboard read model and aggregation logic
- `src/presentation/http/` and `src/infrastructure/health.py` — authenticated advisor dashboard API and page rendering
- `src/infrastructure/container.py` — DI wiring for the dashboard service
- `tests/` — dashboard service, advisor HTTP route, and page behavior coverage
- `docs/` — phase spec/plan, architecture notes, and handoff state

## Prerequisites (Manual)
- [ ] None

## Implementation Steps
### Group 1
#### [x] Step 1: Define the dashboard read model and aggregation service
- **Files:** new advisor dashboard model/service under `src/domain/models/` and `src/application/services/`
- **Action:** Implement period-aware advisor aggregation for KPIs, trend series, category breakdowns, month-only budget status, and empty-state metadata while preserving milliunit invariants.
- **Tests:** Add focused unit tests for period handling, trend generation, category ranking, and empty-state behavior.

### Group 2 (depends on: Group 1)
#### [x] Step 2: Wire the advisor dashboard API
- **Files:** `src/presentation/http/server.py`, `src/presentation/http/handlers/advisor_api_handler.py`, `src/infrastructure/container.py`
- **Action:** Add `GET /api/v1/advisor/dashboard`, validate the `period` parameter, reuse the existing advisor session check, and return a stable advisor dashboard JSON payload without overloading bootstrap.
- **Tests:** Extend advisor HTTP tests for authenticated success, auth failure, invalid period, and method enforcement.

### Group 3 (depends on: Group 2)
#### [x] Step 3: Replace the placeholder advisor page with the dashboard UI
- **Files:** `src/presentation/http/handlers/advisor_page_handler.py`
- **Action:** Replace the placeholder landing page with a server-served month-first dashboard that fetches bootstrap + dashboard payloads, renders summary cards, trend, categories, period switching, and Spanish onboarding/empty states.
- **Tests:** Extend advisor page tests for authenticated rendering and unchanged logout behavior.

### Group 4 (depends on: Group 3)
#### [x] Step 4: Update architecture docs, plan state, and handoff state
- **Files:** `docs/ARCHITECTURE.md`, `docs/wip_state.md`, this plan file
- **Action:** Document the new dashboard baseline, mark completed steps, and leave the repo ready for the next advisor phase.
- **Tests:** N/A

## Constraints & Architecture
- Keep the current single-repo, single-server advisor baseline from the existing ADRs.
- Do not introduce a frontend framework, build pipeline, monorepo split, or separate advisor service.
- Keep advisor user-facing strings in Spanish.
- Preserve the existing advisor session/cookie contract and the existing shared bearer-token expense API behavior.
- Maintain per-user isolation and YNAB milliunit invariants in all new aggregations.

## Verification
- [x] `.venv/bin/pytest tests/test_advisor_dashboard_service.py tests/test_advisor_http.py tests/test_http_server.py tests/test_container.py tests/test_advisor_access_service.py tests/test_health.py`
- [ ] Manual advisor smoke test through the existing `/analisis` launch flow in the current HTTP runtime
