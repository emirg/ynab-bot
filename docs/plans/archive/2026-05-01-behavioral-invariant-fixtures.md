# Plan: Behavioral Invariant Fixtures

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-behavioral-invariant-fixtures.md`
- **Goal:** Add executable financial behavior fixtures to the existing harness so Railway blocks deploys when high-risk financial rules drift.
- **Approach:** Implement a standard-library fixture runner, adapt its results into existing harness `Finding` objects, expose a direct advisory CLI, and cover the integration with focused harness tests.
- **Harness Roadmap Marker:** E.23 — Behavioral Invariant Fixtures

## Affected Components
- `scripts/harness/behavioral_invariants.py` — new executable fixture runner.
- `scripts/harness/check_behavioral_invariants.py` — new direct advisory CLI.
- `scripts/harness/checks.py` — wire behavioral fixture findings into `run_checks()`.
- `scripts/harness/commands.py` — register the new local command.
- `docs/harness/COMMANDS.md` — document the new command.
- `tests/harness/test_checks.py` — fixture-level pass/fail coverage.
- `tests/harness/test_repository_docs.py` — repo-level CLI JSON coverage.
- `docs/adrs/2026-04-30-executable-harness-gates.md` — record the new harness slice.
- `ROADMAP.md` and `docs/wip_state.md` — close-out state.

## Prerequisites (Manual)
- [x] No external service credentials or manual Railway changes required.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Add the executable fixture surface. -->

#### [x] Step 1: Implement fixture runner
- **Files:** `scripts/harness/behavioral_invariants.py`
- **Action:** Add deterministic fixtures for split spending, net spending, category snapshots, edit reconciliation, and undo strictness. Return structured pass/fail results without calling external services.
- **Tests:** `tests/harness/test_checks.py` — passing fixture repo and deliberate failure repo scenarios.

### Group 2 (depends on: Group 1)
<!-- Wire runner into harness interfaces. -->

#### [x] Step 2: Wire harness and CLI
- **Files:** `scripts/harness/checks.py`, `scripts/harness/check_behavioral_invariants.py`
- **Action:** Convert fixture results into `Finding` objects, include them in `run_checks()`, and expose text/JSON output with strict advisory behavior.
- **Tests:** `tests/harness/test_repository_docs.py` — direct CLI JSON coverage.

#### [x] Step 3: Register command
- **Files:** `scripts/harness/commands.py`, `docs/harness/COMMANDS.md`
- **Action:** Add the direct behavioral invariant command to the command registry and living command document.
- **Tests:** Existing command-registry harness checks.

### Group 3 (depends on: Group 2)
<!-- Documentation close-out. -->

#### [x] Step 4: Close documentation state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/specs/archive/2026-05-01-behavioral-invariant-fixtures.md`, `docs/plans/archive/2026-05-01-behavioral-invariant-fixtures.md`, `docs/wip_state.md`
- **Action:** Update the ADR and roadmap marker, mark implementation docs complete, archive SPEC/PLAN, and update handoff state.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`

## Constraints & Architecture
- Use only the Python standard library in harness code.
- Do not call external services, network APIs, databases, or pytest from `verify.py --ci`.
- Preserve YNAB as the financial source of truth.
- Keep `/editar` identity-based and `/deshacer` strict for destructive deletes.
- Keep command documentation registry-backed.

## Verification
- [x] `.venv/bin/python scripts/harness/check_behavioral_invariants.py --json`
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
