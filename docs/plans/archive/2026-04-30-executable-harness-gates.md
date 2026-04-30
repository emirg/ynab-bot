# Plan: Executable Harness Gates

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.11
- **Source Spec:** `docs/specs/archive/2026-04-30-executable-harness-gates.md`
- **Goal:** Add standard-library harness commands that validate documentation workflow state locally and block Railway builds on violations.
- **Approach:** Implement reusable Python checks under `scripts/harness/`, wrap them with advisory and CI CLIs, clean existing documentation drift, wire Railway build verification, and record the harness policy in an ADR.

## Affected Components
- `scripts/harness/checks.py` — reusable documentation workflow checks and output formatting.
- `scripts/harness/check_docs.py` — advisory CLI.
- `scripts/harness/verify.py` — CI CLI.
- `tests/harness/` — focused unit tests and repository-state verification.
- `railway.toml` — run harness verification before pytest.
- `docs/specs/`, `docs/plans/`, `docs/adrs/` — feature documentation and drift cleanup.
- `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.claude/agents/` — agent entrypoint/context cleanup.
- `docs/ARCHITECTURE.md` — Railway build command refresh.

## Prerequisites (Manual)
- [x] None.

## Implementation Steps

### Group 1

#### [x] Step 1: Add failing harness tests
- **Files:** `tests/harness/test_checks.py`, `tests/harness/test_repository_docs.py`
- **Action:** Define expected behavior for required files, active SPEC/PLAN metadata, ADR references, agent entrypoints, stale orchestration references, advisory/CI exit behavior, and current repository pass state.
- **Tests:** Run `.venv/bin/pytest tests/harness -q` and confirm failures are caused by missing harness implementation/current drift.

### Group 2 (depends on: Group 1)

#### [x] Step 2: Implement reusable documentation checks
- **Files:** `scripts/harness/checks.py`, `scripts/harness/__init__.py`
- **Action:** Add standard-library-only parsers and checks with grouped PASS/WARN/FAIL findings.
- **Tests:** `tests/harness/test_checks.py`.

#### [x] Step 3: Add CLI wrappers
- **Files:** `scripts/harness/check_docs.py`, `scripts/harness/verify.py`
- **Action:** Add advisory and CI command entrypoints. Advisory mode exits zero by default; strict/CI mode exits nonzero on FAIL findings.
- **Tests:** `tests/harness/test_checks.py`.

### Group 3 (depends on: Group 2)

#### [x] Step 4: Clean current documentation and agent drift
- **Files:** `docs/specs/archive/2026-04-12-resumen-mensual-compacto.md`, `docs/plans/archive/2026-04-12-resumen-mensual-compacto.md`, `docs/plans/archive/2026-03-21-financial-advisor-web-design.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/agents/*.md`, `docs/ARCHITECTURE.md`, `README.md`
- **Action:** Archive completed active docs, archive the compatibility pointer, replace stale orchestration references, and refresh outdated SQLite/current pytest context.
- **Tests:** `tests/harness/test_repository_docs.py`.

### Group 4 (depends on: Group 3)

#### [x] Step 5: Wire Railway and ADR
- **Files:** `railway.toml`, `docs/adrs/2026-04-30-executable-harness-gates.md`
- **Action:** Run `python scripts/harness/verify.py --ci && pytest` in Railway build and record the long-lived harness enforcement decision.
- **Tests:** repository-level harness test plus direct command execution.

### Group 5 (depends on: Group 4)

#### [x] Step 6: Final review and archive feature docs
- **Files:** `docs/specs/archive/2026-04-30-executable-harness-gates.md`, `docs/plans/archive/2026-04-30-executable-harness-gates.md`, `docs/wip_state.md`
- **Action:** Review implementation against the SPEC, archive implemented SPEC/PLAN, update ADR references to archive paths, and refresh handoff state.
- **Tests:** Full verification commands listed below.

## Constraints & Architecture
- Use only Python standard-library modules in `scripts/harness/`.
- Do not add database migrations or runtime financial behavior changes.
- Keep harness output deterministic enough for CI logs.
- Preserve the project invariants in `docs/AI_WORKFLOW.md`; this feature only enforces documentation workflow state.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
