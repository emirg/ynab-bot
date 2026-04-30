# Plan: Railway Config Harness

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-04-30-railway-config-harness.md`
- **Harness Roadmap Marker:** E.19
- **Goal:** Extend the existing harness so Railway deploy configuration drift is detected locally and in CI.
- **Approach:** Add standard-library TOML parsing checks to `scripts/harness/checks.py`, cover behavior with focused harness tests, then archive the completed SPEC/PLAN and update roadmap/ADR references.

## Affected Components
- `scripts/harness/checks.py` — add Railway config parsing and finding generation.
- `tests/harness/test_checks.py` — add fixture-level behavior coverage for Railway config cases.
- `tests/harness/test_repository_docs.py` — rely on the aggregate repo harness check instead of string-only Railway assertions.
- `ROADMAP.md` — add the completed E.19 roadmap entry.
- `docs/adrs/2026-04-30-executable-harness-gates.md` — record deploy-config checks as part of the harness policy.

## Prerequisites (Manual)
- [x] User approved the Railway config harness slice.
- [x] No live Railway CLI access is required.

## Implementation Steps

### Group 1
<!-- Test-first coverage for the new behavior. -->

#### [x] Step 1: Add failing Railway config harness tests
- **Files:** `tests/harness/test_checks.py`
- **Action:** Add tests for valid Railway config, missing file, malformed TOML, missing harness command, pytest before harness, and wrong start command.
- **Tests:** `tests/harness/test_checks.py` — new tests should fail before implementation because the aggregate harness does not validate Railway config yet.

### Group 2 (depends on: Group 1)
<!-- Implement the parser and checks. -->

#### [x] Step 2: Implement Railway config checks
- **Files:** `scripts/harness/checks.py`
- **Action:** Use `tomllib` to parse `railway.toml`; add order-aware build command validation and start command validation; include checks in `run_checks()`.
- **Tests:** `tests/harness/test_checks.py` — new tests pass.

### Group 3 (depends on: Group 2)
<!-- Documentation closeout and repo verification. -->

#### [x] Step 3: Update roadmap, ADR, and archive completed docs
- **Files:** `ROADMAP.md`, `docs/adrs/2026-04-30-executable-harness-gates.md`, `docs/specs/2026-04-30-railway-config-harness.md`, `docs/plans/2026-04-30-railway-config-harness.md`
- **Action:** Add E.19, update ADR references and context, mark SPEC/PLAN complete, archive both docs with roadmap markers.
- **Tests:** `scripts/harness/verify.py --ci`, `tests/harness`.

## Constraints & Architecture
- Keep the harness dependency-free and import-safe before application dependencies are loaded.
- Do not call Railway or require network access.
- Keep existing CLI contracts unchanged.
- Preserve JSON output shape.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
