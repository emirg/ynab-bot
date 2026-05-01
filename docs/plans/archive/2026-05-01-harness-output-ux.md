# Plan: Harness Output UX

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-harness-output-ux.md`
- **Harness Roadmap Marker:** E.27 — Harness Output UX
- **Goal:** Make harness diagnostics easier to scan locally and in Railway logs while preserving existing command behavior.
- **Approach:** Improve formatting and optional metadata in the shared harness output layer, then update focused tests without changing check semantics.

## Affected Components
- `scripts/harness/checks.py` — shared `Finding` model and text/JSON formatting.
- `scripts/harness/check_docs.py` — verify output remains compatible.
- `scripts/harness/check_financial_invariants.py` — verify direct command output remains compatible.
- `scripts/harness/check_behavioral_invariants.py` — verify direct command output remains compatible.
- `scripts/harness/verify.py` — verify CI behavior remains compatible.
- `tests/harness/test_checks.py` — formatting and exit-code contract coverage.
- `tests/harness/test_repository_docs.py` — repo-level JSON CLI coverage.
- `docs/harness/COMMANDS.md`, `ROADMAP.md`, `docs/wip_state.md` — close-out updates if needed.

## Prerequisites (Manual)
- [x] Decide whether E.27 should be implemented before or after E.25/E.26.
- [x] Decide whether the first UX slice should add optional check-family metadata or only revise text formatting.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Output design lock. -->

#### [x] Step 1: Choose output shape
- **Files:** `docs/plans/2026-05-01-harness-output-ux.md`
- **Action:** Selected to add `family` and `hint` optional metadata to the `Finding` dataclass.
  - **Text Output**: Improve visual separation of groups and include family/hint if present.
  - **JSON Output**: Add `family` and `hint` keys to finding objects while keeping `summary` and `findings` root keys.
- **Tests:** None.

### Group 2 (depends on: Group 1)
<!-- Shared formatter implementation. -->

#### [x] Step 2: Update shared formatter
- **Files:** `scripts/harness/checks.py`
- **Action:** Improved text formatting with family grouping and hints. Added `family` and `hint` to `Finding` dataclass and JSON output.
- **Tests:** `tests/harness/test_checks.py` — pass/warn/fail grouping and JSON compatibility.

### Group 3 (depends on: Group 2)
<!-- Command compatibility and close-out. -->

#### [x] Step 3: Verify command contracts
- **Files:** `tests/harness/test_repository_docs.py`
- **Action:** Ensured all direct harness commands still return expected exit codes and valid JSON.
- **Tests:** `.venv/bin/pytest tests/harness -q`.

#### [x] Step 4: Close documentation state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/wip_state.md`, archived SPEC/PLAN.
- **Action:** Marked implementation complete and archived docs.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`.

## Constraints & Architecture
- Preserve all current command names and exit-code behavior.
- Do not add non-standard-library formatting dependencies.
- Keep JSON backwards-compatible.
- Keep output deterministic for tests and deploy logs.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/check_financial_invariants.py --json`
- [x] `.venv/bin/python scripts/harness/check_behavioral_invariants.py --json`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
