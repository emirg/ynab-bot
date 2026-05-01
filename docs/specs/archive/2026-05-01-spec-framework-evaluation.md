# Spec: Spec Framework Evaluation

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.21
- **Harness Roadmap Marker:** E.21
- **Related ADRs:** `docs/adrs/2026-05-01-spec-framework-evaluation.md`

## Summary
Evaluate OpenSpec, OpenSDD, OpenSPDD/SPDD, and Superpowers against this repository's existing SPEC/PLAN/ADR workflow and executable harness. The outcome should be a documented adoption decision rather than a tool installation or process migration.

## Problem
- The harness ADR deferred OpenSpec/OpenSDD evaluation until after baseline workflow enforcement existed.
- The repo now has executable checks for documentation lifecycle, roadmap coherence, Railway deploy configuration, and command references.
- Adding another workflow framework without a decision record could duplicate existing process or introduce conflicting artifacts.

## Goals
- Compare each candidate framework by fit, overlap, risk, and useful ideas.
- Decide whether to adopt, defer, reject, or selectively borrow practices.
- Record the decision in an ADR with source references.
- Keep the evaluation lightweight and avoid tool installation in this slice.

## Non-Goals
- Do not install OpenSpec, OpenSDD, OpenSPDD, or Superpowers.
- Do not migrate existing `docs/specs`, `docs/plans`, or ADRs.
- Do not add new harness code in this slice.
- Do not create a full enterprise prompt-governance program.

## Users / Consumers
- Maintainers deciding how far to evolve the harness.
- AI agents following the repo's workflow.
- Future contributors evaluating whether external SDD/SPDD tooling belongs in the project.

## Expected Behavior
- The repo gains an accepted ADR with a concrete recommendation.
- The roadmap records the evaluation as completed.
- Future harness work can refer to the decision rather than reopening the same question.

## Inputs and Outputs
- **Inputs:** Current repo docs/harness, public references for OpenSpec, OpenSDD, OpenSPDD/SPDD, and Superpowers.
- **Outputs:** ADR, archived SPEC/PLAN, updated ROADMAP.
- **Public Interfaces:** Documentation only.

## Business Rules and Constraints
- The current `SPEC -> PLAN -> IMPLEMENT -> REVIEW -> DONE` workflow remains authoritative during the evaluation.
- The decision must account for this repo's financial invariants and YNAB source-of-truth rules.
- Recommendations should favor executable local checks over unenforced ceremony.

## Edge Cases and Failure Handling
- If a candidate has ambiguous branding or multiple projects with similar names, identify the evaluated source.
- If a framework has useful practices but high adoption cost, separate "borrow the idea" from "install the tool."

## Acceptance Criteria
- [x] ADR compares OpenSpec, OpenSDD, OpenSPDD/SPDD, and Superpowers.
- [x] ADR states a concrete decision and follow-up path.
- [x] ROADMAP records the completed evaluation.
- [x] Current harness verification passes after archiving the evaluation docs.

## Open Questions
- None.

## References
- https://openspec.dev/
- https://github.com/Fission-AI/OpenSpec
- https://opensdd.ai/
- https://github.com/gszhangwei/open-spdd
- https://martinfowler.com/articles/structured-prompt-driven/
- https://github.com/obra/superpowers
