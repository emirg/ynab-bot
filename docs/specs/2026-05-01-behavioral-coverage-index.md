# Spec: Behavioral Coverage Index

## Metadata
- **Status:** Approved
- **Owner:** Codex
- **Related Roadmap Item:** E.25 — Behavioral Coverage Index
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`

## Summary
The behavioral invariant manifest identifies each executable fixture, its owner, and the protected rule. This feature extends that manifest into a coverage index by linking each protected rule to pytest evidence and documentation or ADR evidence.

## Problem
- The manifest proves that behavioral fixtures have ownership metadata, but it does not prove that those fixtures are also supported by normal pytest coverage.
- Financial invariant evidence and behavioral fixture evidence are currently checked by separate mechanisms.
- Future high-risk financial rules need a clear way to show source ownership, executable harness coverage, pytest evidence, and documentation source-of-truth in one place.

## Goals
- Extend behavioral fixture metadata with pytest evidence and doc/ADR evidence.
- Validate that evidence paths exist and required snippets or test names are present.
- Keep the behavioral harness output concise while making missing coverage actionable.
- Preserve the current direct behavioral command and CI gate behavior.

## Non-Goals
- Add new behavioral scenarios.
- Replace the existing financial invariant evidence checks in one step.
- Introduce external schema validation, YAML, OpenSPDD, or generated prompt artifacts.
- Run pytest from the harness.

## Users / Consumers
- Maintainers adding or reviewing high-risk financial invariants.
- AI agents deciding whether a financial behavior has sufficient source, test, and documentation coverage.
- Railway deploy builds using `scripts/harness/verify.py --ci`.

## Expected Behavior
- Each behavioral fixture declares pytest evidence and doc/ADR evidence in `scripts/harness/behavioral_invariants.toml`.
- The harness validates that each evidence file exists and contains the declared snippets or test names.
- Missing coverage evidence produces `FAIL` findings in both direct behavioral diagnostics and `verify.py --ci`.
- Passing output remains grouped and readable, with one pass per protected behavioral invariant.

## Inputs and Outputs
- **Inputs:** `scripts/harness/behavioral_invariants.toml`, source files, pytest files, docs/ADR files.
- **Outputs:** Harness findings in text or JSON.
- **Public Interfaces:** `.venv/bin/python scripts/harness/check_behavioral_invariants.py`, `.venv/bin/python scripts/harness/verify.py --ci`.

## Business Rules and Constraints
- Use only Python standard-library parsing and validation.
- Evidence entries must support file paths and snippets.
- Validation must not execute pytest or import test modules.
- Existing financial invariants remain authoritative: milliunits, YNAB source of truth, financial read matrix, per-user isolation, and Spanish UI for user-facing strings.

## Edge Cases and Failure Handling
- Missing evidence sections fail the specific behavioral fixture.
- Missing evidence paths fail with the fixture ID and path.
- Missing snippets fail with the fixture ID, path, and snippet.
- Duplicate evidence entries should be accepted but do not add value; implementation may deduplicate internally.

## Acceptance Criteria
- [ ] Behavioral fixture manifest supports pytest and doc evidence metadata.
- [ ] Harness validates all configured evidence paths and snippets.
- [ ] Focused tests cover missing path and missing snippet failures.
- [ ] Direct behavioral diagnostics and CI harness pass after current evidence is indexed.

## Open Questions
- None.

## References
- `scripts/harness/behavioral_invariants.toml`
- `scripts/harness/behavioral_invariants.py`
- `scripts/harness/checks.py`
- `docs/specs/archive/2026-05-01-behavioral-invariant-manifest.md`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
