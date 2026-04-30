# Spec: Harness Roadmap Coherence

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.18
- **Owner:** Codex
- **Related Roadmap Item:** E.12 — Harness Roadmap Coherence
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`

## Summary
The executable harness should become easier to consume by machines and stricter about documentation graph coherence. This slice adds JSON output, enforces completed PLAN checklist hygiene, and verifies that implemented SPEC/PLAN history is represented in `ROADMAP.md`. When implemented features are missing from the roadmap, the roadmap must be updated so it remains the current project index.

## Problem
- Harness diagnostics are human-readable only, which limits CI and future automation usage.
- Completed PLANs can be archived with unchecked implementation or verification items, weakening the documentation lifecycle signal.
- Archived SPEC/PLAN features can exist without a corresponding `ROADMAP.md` entry, so the roadmap can drift behind completed work.

## Goals
- Add a stable `--json` output mode to both harness CLIs.
- Validate that completed archived PLANs have all markdown task checkboxes checked.
- Validate that implemented archived SPEC/PLAN features are represented in `ROADMAP.md`.
- Update `ROADMAP.md` with missing implemented features discovered during this work.

## Non-Goals
- Introduce OpenSpec/OpenSDD or any external documentation framework.
- Enforce semantic equivalence between roadmap prose and every acceptance criterion.
- Require roadmap entries for historical documents that do not represent feature completion, such as compatibility pointers or superseded drafts.

## Users / Consumers
- Maintainers and agents reading CI output.
- Future automation that needs structured harness findings.
- Project planners relying on `ROADMAP.md` as the current completed-work index.

## Expected Behavior
- `scripts/harness/check_docs.py --json` prints valid JSON with summary counts and finding records.
- `scripts/harness/verify.py --ci --json` prints the same JSON format and still exits nonzero on FAIL findings.
- Completed archived PLANs with unchecked `- [ ]` items produce FAIL findings.
- Implemented archived SPECs and completed archived PLANs produce FAIL findings when no roadmap marker represents them.
- `ROADMAP.md` contains entries for the implemented SPEC/PLAN features that were missing from the roadmap.

## Inputs and Outputs
- **Inputs:** `docs/specs/archive/*.md`, `docs/plans/archive/*.md`, `ROADMAP.md`, harness CLI args.
- **Outputs:** Human-readable diagnostics, JSON diagnostics, harness exit codes, and updated roadmap entries.
- **Public Interfaces:** `--json` on `scripts/harness/check_docs.py` and `scripts/harness/verify.py`.

## Business Rules and Constraints
- Harness implementation remains standard-library only.
- JSON output must be deterministic and include enough data for automation: severity counts, total count, and findings with severity/message/path.
- Completed archived PLANs must not contain unchecked markdown task boxes.
- Roadmap coherence is based on explicit metadata markers in archived SPEC/PLAN docs, not fuzzy natural-language matching.
- Historical docs that are compatibility pointers, superseded drafts, or not feature-completion records may opt out with explicit harness metadata.

## Edge Cases and Failure Handling
- A malformed JSON mode must fail tests before shipping.
- Missing `ROADMAP.md` produces a FAIL.
- Archived PLANs without `Completed` status are ignored by completed-plan checklist enforcement.
- Archived SPECs without `Implemented` status are ignored by implemented-feature roadmap enforcement.
- Existing archived documents may be annotated with harness metadata when they are historical exceptions.

## Acceptance Criteria
- [x] JSON output is covered by tests and valid for both CLIs.
- [x] Completed archived PLAN checkbox enforcement is covered by tests.
- [x] ROADMAP coherence enforcement is covered by tests.
- [x] Current repository passes `.venv/bin/python scripts/harness/verify.py --ci`.
- [x] `ROADMAP.md` includes missing implemented features discovered from archived SPEC/PLAN history.

## Open Questions
- None.

## References
- `docs/specs/archive/2026-04-30-executable-harness-gates.md`
- `docs/plans/archive/2026-04-30-executable-harness-gates.md`
- `scripts/harness/checks.py`
- `ROADMAP.md`
