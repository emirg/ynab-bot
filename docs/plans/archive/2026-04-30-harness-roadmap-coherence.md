# Plan: Harness Roadmap Coherence

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.18
- **Source Spec:** `docs/specs/archive/2026-04-30-harness-roadmap-coherence.md`
- **Goal:** Extend the documentation harness with JSON output, ROADMAP coherence checks, completed-plan checklist checks, and update ROADMAP to reflect completed implemented docs.
- **Approach:** Add failing harness tests first, implement small reusable parser/output helpers, annotate or update archived docs where needed, then archive this feature documentation after verification.

## Affected Components
- `scripts/harness/checks.py` — JSON formatting, roadmap marker parsing, completed-plan checklist checks.
- `scripts/harness/check_docs.py` — `--json` CLI flag.
- `scripts/harness/verify.py` — `--json` CLI flag.
- `tests/harness/test_checks.py` — focused behavior coverage.
- `tests/harness/test_repository_docs.py` — checked-in ROADMAP and CLI behavior coverage.
- `ROADMAP.md` — add missing completed feature entries.
- `docs/specs/archive/`, `docs/plans/archive/` — add explicit harness roadmap metadata or exceptions where needed.
- `docs/wip_state.md` — final handoff state.

## Prerequisites (Manual)
- [x] None.

## Implementation Steps

### Group 1

#### [x] Step 1: Add failing tests for JSON output and stricter doc graph checks
- **Files:** `tests/harness/test_checks.py`, `tests/harness/test_repository_docs.py`
- **Action:** Test JSON output shape, CLI `--json`, completed archived PLAN unchecked checkbox failures, implemented SPEC/PLAN roadmap marker failures, and repository pass state.
- **Tests:** `.venv/bin/pytest tests/harness -q` should fail for missing behavior.

### Group 2 (depends on: Group 1)

#### [x] Step 2: Implement JSON output
- **Files:** `scripts/harness/checks.py`, `scripts/harness/check_docs.py`, `scripts/harness/verify.py`
- **Action:** Add deterministic JSON formatting and wire `--json` into both CLIs without changing default human output.
- **Tests:** `tests/harness/test_checks.py`.

#### [x] Step 3: Implement completed-plan and roadmap coherence checks
- **Files:** `scripts/harness/checks.py`
- **Action:** Add archived PLAN checkbox enforcement and roadmap marker validation based on explicit harness metadata.
- **Tests:** `tests/harness/test_checks.py`.

### Group 3 (depends on: Group 2)

#### [x] Step 4: Bring current docs and roadmap into coherence
- **Files:** `ROADMAP.md`, relevant archived SPEC/PLAN docs
- **Action:** Add missing ROADMAP completed entries and explicit `Harness Roadmap Marker` or `Harness Roadmap: Ignore` metadata to archived docs.
- **Tests:** `tests/harness/test_repository_docs.py`.

### Group 4 (depends on: Group 3)

#### [x] Step 5: Final review and archive docs
- **Files:** `docs/specs/archive/2026-04-30-harness-roadmap-coherence.md`, `docs/plans/archive/2026-04-30-harness-roadmap-coherence.md`, `docs/wip_state.md`
- **Action:** Review implementation against the SPEC, archive implemented docs, update roadmap, and refresh handoff state.
- **Tests:** Full verification commands listed below.

## Constraints & Architecture
- Keep harness code standard-library only.
- Do not touch runtime financial behavior.
- Use explicit metadata for ROADMAP coherence to avoid brittle fuzzy matching.
- Existing human-readable harness output remains the default.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/check_docs.py --json`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
