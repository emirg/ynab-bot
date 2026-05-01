# ADR: Spec Framework Evaluation

## Metadata
- **Status:** Accepted
- **Date:** 2026-05-01
- **Related Spec:** `docs/specs/archive/2026-05-01-spec-framework-evaluation.md`
- **Related Plan:** `docs/plans/archive/2026-05-01-spec-framework-evaluation.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The executable harness now enforces the repository's documentation lifecycle, roadmap coherence, Railway deploy configuration, and command registry. The earlier harness ADR intentionally deferred evaluation of OpenSpec/OpenSDD until this baseline existed.

The user asked to evaluate four related approaches:

- **OpenSpec:** evaluated as Fission-AI OpenSpec, the current open-source SDD tool at `openspec.dev` / `github.com/Fission-AI/OpenSpec`.
- **OpenSDD:** evaluated as the open-standard, Markdown/Git/YAML-oriented methodology at `opensdd.ai`.
- **OpenSPDD / SPDD:** evaluated as `gszhangwei/open-spdd`, which implements the SPDD workflow described by Thoughtworks on Martin Fowler's site.
- **Superpowers:** evaluated as `obra/superpowers`, the agentic skills workflow already available in this environment.

The project already has a lightweight local equivalent of several SDD ideas: SPECs define behavior, PLANs define execution, ADRs define durable decisions, ROADMAP is the completion index, and the harness makes drift executable.

## Decision
Do not adopt OpenSpec, OpenSDD, or OpenSPDD as a project dependency or required folder structure now.

Keep the current repo-native SPEC/PLAN/ADR workflow as the source of truth, with the executable harness as the enforcement layer.

Selectively borrow the following ideas:

- From **OpenSpec:** spec deltas and change-folder review are useful concepts, but this repo already has date-based SPEC/PLAN artifacts plus ROADMAP markers. Revisit if the project grows enough that a separate `openspec/changes` lifecycle would reduce review cost.
- From **OpenSDD:** open standards and tool-agnostic Markdown/Git/YAML alignment match the existing workflow. Treat OpenSDD as philosophical validation, not a migration target.
- From **OpenSPDD/SPDD:** the REASONS Canvas and prompt/code synchronization are useful for complex, logic-heavy financial changes. Borrow a lightweight "runtime invariant canvas" pattern for future financial safety harness work, but do not install `openspdd` or generate command templates yet.
- From **Superpowers:** continue using relevant skills opportunistically for brainstorming, TDD, debugging, planning, and verification. Do not make Superpowers the repository's canonical workflow because AGENTS/AI_WORKFLOW must remain tool-agnostic across Codex, Claude, Gemini, and other agents.

## Alternatives Considered
- **Adopt OpenSpec immediately:** Rejected for now. It is strong for structured change folders, proposal/design/tasks/spec deltas, and multi-agent tool support, but it would duplicate active SPEC/PLAN/ADR artifacts and require migrating process before there is clear pain.
- **Adopt OpenSDD as the umbrella process:** Rejected as a formal dependency. Its open-standard principles fit the repo, but the current workflow already follows the same Markdown/Git-centered direction and has custom enforcement.
- **Adopt OpenSPDD for every feature:** Rejected as too heavy for routine bot changes. SPDD's prompt-first synchronization is compelling for complex financial logic, but it would add new generated prompt artifacts and commands before the team knows which parts improve outcomes.
- **Make Superpowers mandatory project process:** Rejected. Superpowers is effective as an agent-side discipline layer, but repo instructions need to be portable and should not depend on one plugin's availability.
- **Do nothing:** Rejected. The evaluation itself is useful because it closes the deferred ADR follow-up and clarifies which ideas are worth borrowing.

## Consequences
- **Positive:** Avoids adding a second, competing spec hierarchy while the current harness is still proving itself.
- **Positive:** Keeps the workflow portable across AI assistants and CI/deploy contexts.
- **Positive:** Establishes a clear path for the next high-value harness work: runtime invariant checks inspired by SPDD safeguards.
- **Negative:** The repo does not gain OpenSpec's CLI validation or change-folder dashboard.
- **Negative:** The repo does not gain OpenSPDD's generated REASONS Canvas or prompt/code sync commands.
- **Follow-up:** Add a runtime invariant harness slice for financial safety checks. Use SPDD concepts lightly: requirements, entities, approach, structure, operations, norms, and safeguards can inform test fixture design without requiring OpenSPDD installation.

## References
- `docs/specs/archive/2026-05-01-spec-framework-evaluation.md`
- `docs/plans/archive/2026-05-01-spec-framework-evaluation.md`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
- OpenSpec: https://openspec.dev/
- OpenSpec repository: https://github.com/Fission-AI/OpenSpec
- OpenSDD: https://opensdd.ai/
- OpenSPDD: https://github.com/gszhangwei/open-spdd
- SPDD article: https://martinfowler.com/articles/structured-prompt-driven/
- Superpowers: https://github.com/obra/superpowers
