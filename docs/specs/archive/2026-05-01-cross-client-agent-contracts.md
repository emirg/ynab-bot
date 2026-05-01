# Spec: Cross-Client Agent Contracts

## Metadata
- **Status:** Implemented
- **Harness Roadmap Marker:** E.30
- **Owner:** Codex
- **Related Roadmap Item:** Harness portability and cross-client agent consistency
- **Related ADRs:** `docs/adrs/2026-05-01-cross-client-agent-contracts.md`

## Summary
The repository already defines logical workflow roles in `docs/AI_WORKFLOW.md`, but the strongest concrete role prompts currently live in Claude-specific `.claude/agents/` files. This feature creates a tool-neutral source of truth for project agent contracts so Claude, Codex, Gemini CLI, and future AI clients can execute the same role expectations even when their subagent mechanisms differ.

## Problem
- Claude has concrete agent definitions under `.claude/agents/`, while Codex and Gemini currently map roles through thinner wrapper docs.
- Tool-specific agent files can drift from each other, which weakens the repository's ability to support deterministic handoffs between AI clients.
- The harness can verify general agent entrypoint hygiene, but it does not yet verify that every logical role has a shared contract and that client wrappers point to it.
- Future agents may follow the role names in `docs/AI_WORKFLOW.md` while missing important role-specific constraints such as scope limits, bootstrap docs, output format, and verification rules.

## Goals
- Establish a repo-local, tool-neutral canonical agent contract under `docs/agents/` for every logical role in `docs/AI_WORKFLOW.md`.
- Keep Claude's `.claude/agents/` usable while making it an adapter or synced target, not the canonical source.
- Update Codex and Gemini wrapper docs so they route role execution through the same canonical contracts.
- Add executable harness checks that fail when role contracts, wrapper mappings, or synced Claude adapters drift.
- Keep the mechanism standard-library friendly and compatible with the existing Railway harness flow.

## Non-Goals
- Replace Claude Code's native agent system.
- Require Codex or Gemini to support Claude's `.claude/agents/` format directly.
- Add a new external orchestration framework.
- Implement runtime bot behavior changes, database migrations, or YNAB API changes.
- Build a full prompt compiler for all possible AI tools in this first slice.

## Users / Consumers
- AI assistants implementing work in this repository.
- Maintainers reviewing whether the repo remains portable across AI clients.
- Harness verification commands that enforce workflow consistency.
- Future AI clients that need to adopt the project roles without copying Claude-specific files by hand.

## Expected Behavior
- A canonical agent contract exists for each logical role:
  - Lead Architect
  - Database Advisor
  - Step Implementer
  - Code Reviewer
  - Test Writer
  - Debugger
  - Refactor Advisor
- Canonical contracts live under `docs/agents/`, a repo-native shared location that is not named for a single AI client or external sync tool.
- `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` tell their client how to use the canonical contracts for each logical role.
- Claude-compatible agent files under `.claude/agents/` remain available and are visibly derived from or mapped to the canonical contracts.
- Codex can use the same contracts by loading the relevant canonical file before spawning or adopting a role.
- Gemini CLI can use the same contracts by loading the relevant canonical file before using its mapped capability or self-role prompt.
- Harness diagnostics report missing role contracts, missing wrapper mappings, and adapter drift in grouped findings.
- CI verification fails when cross-client agent contract requirements are violated.

## Inputs and Outputs
- **Inputs:** `docs/AI_WORKFLOW.md`, `docs/agents/`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/agents/`, optional Skillshare sync configuration, and harness commands.
- **Outputs:** Shared agent contract markdown files, refreshed client wrappers, harness PASS/WARN/FAIL findings, and optional ADR documentation for the canonical-agent-contract decision.
- **Public Interfaces:** `.venv/bin/python scripts/harness/check_docs.py`, `.venv/bin/python scripts/harness/verify.py --ci`, and the repo's root AI wrapper docs.

## Business Rules and Constraints
- `docs/AI_WORKFLOW.md` remains the source of truth for the logical role list.
- The canonical role contracts must be tool-neutral and must not require Claude-only frontmatter to understand the role.
- Tool-specific adapters may include client-specific metadata, but the behavioral contract must point back to the canonical role file.
- Skillshare may be used later to distribute or sync adapters, but correctness must not depend on the Skillshare CLI being installed or configured.
- Harness checks must use only the Python standard library.
- Existing project invariants still apply: YNAB source of truth, milliunits, dependency injection, per-user isolation, Spanish user-facing strings, and required tests for new modules.
- The feature must not silently remove Claude agent functionality; Claude users should keep native `.claude/agents/` behavior.
- Client wrapper docs must stay thin and must not duplicate the full shared contracts.

## Edge Cases and Failure Handling
- If a logical role is added to `docs/AI_WORKFLOW.md` without a canonical contract, harness verification should fail and identify the missing role.
- If a canonical contract exists but a wrapper doc does not map that role, harness verification should fail and identify the wrapper.
- If `.claude/agents/` contains an adapter for a role but does not reference its canonical contract, harness verification should fail or warn according to the drift severity chosen in the plan.
- If Skillshare is unavailable locally, the repo must still remain understandable and verifiable from committed files.
- If a client lacks native subagents, it must adopt the role itself using the canonical contract.

## Acceptance Criteria
- [x] Every logical role in `docs/AI_WORKFLOW.md` has one canonical agent contract file under `docs/agents/`.
- [x] `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` map every logical role to the canonical contract and the client's execution mechanism.
- [x] `.claude/agents/` remains usable for Claude and each Claude agent references its canonical contract.
- [x] Harness tests cover missing canonical contracts, missing wrapper mappings, and Claude adapter drift.
- [x] `.venv/bin/python scripts/harness/verify.py --ci` fails on cross-client contract violations.
- [x] `.venv/bin/python scripts/harness/verify.py --ci` passes on the checked-in repository after implementation.
- [x] The feature is documented with an ADR if the canonical contract location or sync policy becomes a long-lived architectural decision.

## Open Questions
- None.

## References
- `docs/AI_WORKFLOW.md`
- `docs/DOCUMENTATION_WORKFLOW.md`
- `docs/harness/COMMANDS.md`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
- `docs/agents/`
- `.claude/agents/`
- `.skillshare/config.yaml`
