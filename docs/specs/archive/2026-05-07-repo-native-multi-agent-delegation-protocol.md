# Spec: Repo-Native Multi-Agent Delegation Protocol

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** Harness portability and multi-agent workflow reliability
- **Related ADRs:** `docs/adrs/2026-05-07-repo-native-multi-agent-delegation-protocol.md`
- **Harness Roadmap Marker:** E.30.1 — Repo-Native Multi-Agent Delegation Protocol

## Summary
The repository already has canonical role contracts and grouped implementation plans, but it does not yet define a repo-native delegation protocol for deciding when work should be delegated to subagents, how parallel work claims ownership, and how results are integrated. This feature formalizes multi-agent delegation as part of the existing SPEC/PLAN/ADR workflow without adopting a Claude-only or external orchestration framework.

## Problem
- `docs/AI_WORKFLOW.md` allows parallel execution when supported by the AI platform, but it does not define reliable spawn criteria, ownership rules, or merge expectations.
- `docs/plans/_TEMPLATE.md` groups parallelizable steps, but the group metadata is prose-only and cannot be checked for unsafe overlap.
- Canonical worker-role contracts exist under `docs/agents/`, but there is no canonical Orchestrator or delegation protocol contract.
- Client-specific wrappers do not say when delegation is preferred, allowed, or prohibited, which makes multi-agent behavior dependent on the current assistant instead of the repository.

## Goals
- Define a tool-neutral multi-agent delegation protocol that works for Claude, Codex, Gemini CLI, and future clients.
- Add a canonical Orchestrator or delegation contract under `docs/agents/`.
- Make plan steps carry enough metadata for safe delegation decisions: role, write scope, read scope, dependencies, verification, and escalation target.
- Add harness checks that detect unsafe or incomplete delegation metadata before implementation starts.
- Preserve the existing documentation lifecycle, YNAB invariants, thin wrapper policy, and standard-library harness approach.

## Non-Goals
- Do not adopt Ruflo, Claude Flow, or another external orchestration framework.
- Do not require every AI client to support native subagents.
- Do not force delegation for all tasks.
- Do not change runtime bot behavior, database schema, YNAB integration, Telegram handlers, or HTTP endpoints.
- Do not loosen the SPEC, PLAN, ADR, review, archive, or handoff workflow.

## Users / Consumers
- AI assistants implementing approved plans in this repository.
- Maintainers reviewing whether a PLAN can be executed safely in parallel.
- Harness commands that verify workflow coherence.
- Future AI clients or adapters that need deterministic delegation rules.

## Expected Behavior
- The repository documents one canonical delegation policy that all clients can read.
- A client with native subagents may delegate work without additional user prompting only when the active client policy allows it and the PLAN proves the work is safe to delegate.
- A client without native subagents must adopt the role locally using the same contract instead of skipping the role.
- PLAN steps declare delegation-relevant metadata in a consistent format.
- Parallel steps must have disjoint write scopes and explicit dependencies.
- Database-sensitive work remains sequential until Database Advisor review is complete.
- The Orchestrator remains responsible for group sequencing, result integration, final review routing, and closeout.
- Worker agents return a consistent summary that includes status, modified files, verification commands, blockers, and next-step context.

## Inputs and Outputs
- **Inputs:** `docs/AI_WORKFLOW.md`, `docs/DOCUMENTATION_WORKFLOW.md`, `docs/plans/_TEMPLATE.md`, `docs/agents/`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/agents/`, and harness checks.
- **Outputs:** Updated workflow docs, a canonical delegation contract, updated plan template metadata, wrapper guidance, harness findings, tests, and ADR documentation.
- **Public Interfaces:** `.venv/bin/python scripts/harness/check_docs.py`, `.venv/bin/python scripts/harness/verify.py --ci`, and the repository's AI workflow documents.

## Business Rules and Constraints
- `docs/AI_WORKFLOW.md` remains the source of truth for the execution pipeline.
- `docs/agents/` remains the source of truth for cross-client role behavior.
- Tool-specific wrappers must stay thin and must not duplicate the full delegation protocol.
- Delegation is allowed only when it preserves project invariants: YNAB source of truth, milliunits, dependency injection, per-user isolation, Spanish user-facing strings, database migration safety, and test coverage.
- Harness changes must use only the Python standard library.
- The protocol must distinguish repository permission from client permission; a client may still require explicit user approval before spawning subagents.
- Plans must prefer sequential execution when dependencies or write ownership are unclear.

## Edge Cases and Failure Handling
- If two steps in the same parallel group claim the same write scope, harness verification should fail.
- If a step is marked delegable but lacks verification, write scope, or role metadata, harness verification should fail or warn according to the final severity policy.
- If a worker reports a blocker outside its assigned scope, the Orchestrator must stop that group and route to Debugger or Lead Architect.
- If a client cannot spawn subagents, it must execute the same role locally and report that delegation was unavailable.
- If implementation discovers that the first metadata schema is too rigid, the plan should revise the schema before adding broad harness enforcement.

## Acceptance Criteria
- [x] A canonical delegation or Orchestrator contract exists under `docs/agents/`.
- [x] `docs/AI_WORKFLOW.md` explains default delegation policy, client permission boundaries, and integration responsibility.
- [x] `docs/plans/_TEMPLATE.md` includes required step metadata for delegation safety.
- [x] `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` map delegation behavior through the canonical contract without duplicating it.
- [x] Harness tests cover missing delegation metadata, overlapping parallel write scopes, missing verification, and valid sequential plans.
- [x] `.venv/bin/python scripts/harness/check_docs.py` reports delegation metadata findings.
- [x] `.venv/bin/python scripts/harness/verify.py --ci` fails on unsafe checked-in delegation metadata.
- [x] Existing harness verification and pytest suite pass after implementation.
- [x] The ADR records the repo-native delegation policy and rejects external orchestration as the correctness path.

## Open Questions
- Checks apply to active plans only; archived historical plans are not backfilled.
- Active plan steps fail CI when required delegation metadata is missing or unsafe.

## References
- `docs/AI_WORKFLOW.md`
- `docs/DOCUMENTATION_WORKFLOW.md`
- `docs/plans/_TEMPLATE.md`
- `docs/agents/`
- `docs/adrs/2026-05-01-cross-client-agent-contracts.md`
- `docs/specs/archive/2026-05-01-cross-client-agent-contracts.md`
- `docs/plans/archive/2026-05-01-cross-client-agent-contracts.md`
