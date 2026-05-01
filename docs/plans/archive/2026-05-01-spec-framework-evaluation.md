# Plan: Spec Framework Evaluation

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-01-spec-framework-evaluation.md`
- **Harness Roadmap Marker:** E.21
- **Goal:** Produce a documented decision on OpenSpec, OpenSDD, OpenSPDD/SPDD, and Superpowers.
- **Approach:** Research current public references, compare against the existing repo workflow and harness, write an ADR, update ROADMAP, then archive this SPEC/PLAN.

## Affected Components
- `docs/adrs/2026-05-01-spec-framework-evaluation.md` — decision record.
- `ROADMAP.md` — completed E.21 entry.
- `docs/specs/2026-05-01-spec-framework-evaluation.md` — source spec.
- `docs/plans/2026-05-01-spec-framework-evaluation.md` — implementation plan.
- `docs/wip_state.md` — handoff state.

## Prerequisites (Manual)
- [x] User requested evaluation of OpenSpec, OpenSDD, OpenSPDD/SPDD, and Superpowers.
- [x] Public references reviewed.

## Implementation Steps

### Group 1
<!-- Documentation-only evaluation. -->

#### [x] Step 1: Write evaluation ADR
- **Files:** `docs/adrs/2026-05-01-spec-framework-evaluation.md`
- **Action:** Compare candidates, make a decision, record consequences and follow-up.
- **Tests:** `.venv/bin/python scripts/harness/verify.py --ci --json`.

### Group 2 (depends on: Group 1)
<!-- Closeout. -->

#### [x] Step 2: Update ROADMAP and archive docs
- **Files:** `ROADMAP.md`, `docs/specs/2026-05-01-spec-framework-evaluation.md`, `docs/plans/2026-05-01-spec-framework-evaluation.md`
- **Action:** Add E.21, mark SPEC/PLAN completed/implemented with roadmap marker, archive both.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`, `.venv/bin/pytest tests/harness -q`.

## Constraints & Architecture
- Do not install external tools.
- Keep the existing documentation workflow authoritative.
- Prefer actionable harness follow-ups over broad process migration.

## Verification
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci --json`
- [x] `.venv/bin/pytest tests/harness -q`
