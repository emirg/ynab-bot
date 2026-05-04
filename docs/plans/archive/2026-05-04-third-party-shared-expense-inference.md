# Plan: Third-Party Shared Expense Inference

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-04-third-party-shared-expense-inference.md`
- **Harness Roadmap Marker:** ### E.32 — Third-Party Shared Expense Inference [COMPLETADO]
- **Goal:** Make third-party-paid shared expense messages deterministic when the user omits "conmigo" or uses "me compro" wording.
- **Approach:** Add parser prompt/examples and tests, then verify the existing service/domain normalized-share path produces the expected shared-account zero-sum transactions.

## Affected Components
- `src/parsers/llm_expense_parser.py` — Clarify operating context and add examples for third-party paid inference.
- `tests/parsers/test_llm_expense_parser.py` — Protect structured parser outputs for "me compro" and implicit 50/50 third-party paid messages.
- `tests/application/services/test_expense_service.py` — Verify parsed forms use the shared account and normalized shares.
- `tests/domain/models/test_domain_models.py` — Verify zero-sum payload shapes for the concrete scenarios.
- `docs/ARCHITECTURE.md`, `README.md`, `ROADMAP.md`, `docs/wip_state.md` — Closeout documentation.

## Prerequisites (Manual)
- [x] User approved the design in the current session.
- [x] No database migration required.

## Implementation Steps

### Group 1
<!-- Lock the desired behavior before prompt/code changes. -->

#### [x] Step 1: Add failing parser prompt/output tests
- **Files:** `tests/parsers/test_llm_expense_parser.py`
- **Action:** Add tests for "Eli me compro un agua oxigenada..." and "Eli gasto 71800 en Pret" expected fields.
- **Tests:** Run the new parser tests and confirm they fail for missing prompt expectations.

#### [x] Step 2: Add failing service/domain behavior tests
- **Files:** `tests/application/services/test_expense_service.py`, `tests/domain/models/test_domain_models.py`
- **Action:** Add tests for shared-account selection, normalized shares, and zero-sum category shape for the two scenarios.
- **Tests:** Run the new tests and confirm any missing behavior is exposed.

### Group 2 (depends on: Group 1)
<!-- Implement the prompt and any minimal defensive behavior needed. -->

#### [x] Step 3: Update parser prompt
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:** Clarify that the bot receives expense-registration messages, so known-person paid/gastó/compró messages imply user involvement by default. Add explicit examples for 100% user responsibility and implicit 50/50.
- **Tests:** Parser tests from Step 1.

#### [x] Step 4: Adjust service only if tests expose a deterministic gap
- **Files:** `src/application/services/expense_service.py`
- **Action:** Keep service behavior unchanged if existing normalized-share defaults cover the scenarios; otherwise add the smallest defensive normalization needed.
- **Tests:** Service tests from Step 2.

### Group 3 (depends on: Group 2)
<!-- Documentation and verification closeout. -->

#### [x] Step 5: Update docs and archive completed SPEC/PLAN
- **Files:** `README.md`, `docs/ARCHITECTURE.md`, `ROADMAP.md`, `docs/specs/archive/2026-05-04-third-party-shared-expense-inference.md`, `docs/plans/archive/2026-05-04-third-party-shared-expense-inference.md`, `docs/wip_state.md`
- **Action:** Document the third-party paid inference rule, mark completed work, archive docs, and update handoff.
- **Tests:** `rtk .venv/bin/python scripts/harness/check_docs.py`

#### [x] Step 6: Final verification
- **Files:** None
- **Action:** Run targeted tests, docs harness, CI harness, and full pytest.
- **Verification:**
  - `rtk .venv/bin/pytest tests/parsers/test_llm_expense_parser.py tests/application/services/test_expense_service.py tests/domain/models/test_domain_models.py`
  - `rtk .venv/bin/python scripts/harness/check_docs.py`
  - `rtk .venv/bin/python scripts/harness/verify.py --ci`
  - `rtk .venv/bin/pytest`

## Constraints & Architecture
- YNAB amounts remain milliunits and expenses negative.
- Shared-account selection remains per-user via split configuration.
- UI/user-facing errors remain Spanish.
- No public HTTP serializer changes.

## Verification
- [x] Parser examples cover both reported regressions.
- [x] Service creates other-paid shared expenses through the shared account.
- [x] Domain payloads are zero-sum with real-category outflow and Splitwise inflow.
- [x] Documentation and full test suite pass.
