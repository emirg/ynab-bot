# Plan: Behavioral Invariant Manifest

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-behavioral-invariant-manifest.md`
- **Goal:** Make behavioral invariant fixtures manifest-driven with explicit ownership and protected-rule metadata.
- **Approach:** Add a TOML manifest, parse and validate it in the existing runner, enrich harness findings, update focused tests, and close out documentation.
- **Harness Roadmap Marker:** E.24 — Behavioral Invariant Manifest

## Affected Components
- `scripts/harness/behavioral_invariants.toml` — new fixture ownership manifest.
- `scripts/harness/behavioral_invariants.py` — load manifest, validate metadata, and execute mapped assertions.
- `scripts/harness/checks.py` — include manifest metadata in behavioral findings.
- `tests/harness/test_checks.py` — update minimal fixture repo and add manifest failure coverage.
- `tests/harness/test_repository_docs.py` — update direct CLI JSON expectations.
- `docs/adrs/2026-04-30-executable-harness-gates.md` — record manifest-driven fixture policy.
- `ROADMAP.md`, `docs/wip_state.md` — close-out state.

## Prerequisites (Manual)
- [x] No external dependencies or service credentials required.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Manifest and runner. -->

#### [x] Step 1: Add manifest and parser
- **Files:** `scripts/harness/behavioral_invariants.toml`, `scripts/harness/behavioral_invariants.py`
- **Action:** Add TOML manifest entries for current fixtures; parse with `tomllib`; validate required fields, duplicate IDs, owner paths, and assertion mappings.
- **Tests:** `tests/harness/test_checks.py` — valid manifest and invalid manifest scenarios.

### Group 2 (depends on: Group 1)
<!-- Harness output and tests. -->

#### [x] Step 2: Enrich harness findings
- **Files:** `scripts/harness/checks.py`
- **Action:** Include risk area and protected rule in behavioral invariant PASS/FAIL messages.
- **Tests:** `tests/harness/test_checks.py`, `tests/harness/test_repository_docs.py`.

### Group 3 (depends on: Group 2)
<!-- Documentation close-out. -->

#### [x] Step 3: Close documentation state
- **Files:** `docs/adrs/2026-04-30-executable-harness-gates.md`, `ROADMAP.md`, `docs/specs/archive/2026-05-01-behavioral-invariant-manifest.md`, `docs/plans/archive/2026-05-01-behavioral-invariant-manifest.md`, `docs/wip_state.md`
- **Action:** Mark complete, archive SPEC/PLAN, update ADR and roadmap, and refresh handoff state.
- **Tests:** Harness and full pytest verification.

## Constraints & Architecture
- Use only Python standard-library parsing and validation.
- Keep assertions mapped explicitly to local functions.
- Do not call external services, databases, or pytest from the harness runner.
- Preserve YNAB source-of-truth and financial read matrix invariants.

## Verification
- [x] `.venv/bin/python scripts/harness/check_behavioral_invariants.py --json`
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/pytest`
