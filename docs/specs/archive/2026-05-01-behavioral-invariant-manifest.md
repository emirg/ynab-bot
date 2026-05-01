# Spec: Behavioral Invariant Manifest

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.24 — Behavioral Invariant Manifest
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`
- **Harness Roadmap Marker:** E.24 — Behavioral Invariant Manifest

## Summary
Behavioral invariant fixtures now execute high-risk financial rules in the harness, but their metadata is embedded in runner code. This feature adds a small manifest so each executable fixture declares its owner path, risk area, protected rule, and assertion mapping.

## Problem
- Behavioral fixtures are harder to grow safely when labels, paths, and assertions are hardcoded together.
- Harness output says which fixture passed or failed, but not the risk area or protected rule it represents.
- Future SPDD-style invariant work needs an explicit ownership map so additions remain reviewable.

## Goals
- Add a repo-local behavioral invariant manifest.
- Validate manifest shape, uniqueness, owner paths, and assertion mappings.
- Drive behavioral fixture execution from manifest metadata.
- Improve harness output with risk area and protected rule context.

## Non-Goals
- Introduce OpenSPDD, OpenSpec, OpenSDD, YAML, or non-standard-library parsing.
- Build a generic plugin system for arbitrary fixture code.
- Replace pytest or broaden behavioral fixtures beyond the current high-risk financial set.

## Users / Consumers
- Maintainers adding future behavioral invariants.
- AI agents reviewing whether a new financial fixture has ownership and rule metadata.
- Railway deploy builds running `scripts/harness/verify.py --ci`.

## Expected Behavior
- The harness reads a manifest before running behavioral fixtures.
- Missing required metadata, duplicate fixture IDs, missing owner files, or unknown assertion names produce `FAIL` findings.
- Passing fixture output includes label, risk area, and protected rule.
- The direct behavioral CLI remains advisory by default and supports JSON output.

## Inputs and Outputs
- **Inputs:** `scripts/harness/behavioral_invariants.toml`, repo source files, in-memory fixture data.
- **Outputs:** Harness `PASS`/`FAIL` findings in text or JSON.
- **Public Interfaces:** `.venv/bin/python scripts/harness/check_behavioral_invariants.py`, `scripts/harness/verify.py --ci`.

## Business Rules and Constraints
- Manifest parsing must use Python standard-library `tomllib`.
- Each fixture must declare `id`, `label`, `risk_area`, `protected_rule`, `owner_path`, and `assertion`.
- Each fixture ID must be unique.
- Each owner path must exist in the checked repository root.
- Assertions must map to explicit runner functions, not dynamic imports or eval.

## Edge Cases and Failure Handling
- A missing manifest produces a single `FAIL` finding.
- Invalid TOML produces a `FAIL` finding with the parser error.
- A malformed fixture entry fails without running that entry.
- Unknown assertions fail without attempting execution.

## Acceptance Criteria
- [x] Behavioral fixture execution is manifest-driven.
- [x] Harness output includes risk area and protected rule metadata.
- [x] Tests cover valid manifest output and malformed manifest failures.
- [x] Existing direct behavioral CLI and CI harness continue to pass.

## Open Questions
- None.

## References
- `scripts/harness/behavioral_invariants.py`
- `scripts/harness/check_behavioral_invariants.py`
- `docs/specs/archive/2026-05-01-behavioral-invariant-fixtures.md`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
