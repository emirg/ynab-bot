# ADR: Cross-Client Agent Contracts

## Metadata
- **Status:** Accepted
- **Date:** 2026-05-01
- **Related Spec:** `docs/specs/archive/2026-05-01-cross-client-agent-contracts.md`
- **Related Plan:** `docs/plans/archive/2026-05-01-cross-client-agent-contracts.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The repository defines logical roles in `docs/AI_WORKFLOW.md`, but concrete role behavior had accumulated mostly in Claude-specific `.claude/agents/` files. That made Claude the accidental source of truth and left Codex, Gemini CLI, and future clients dependent on thinner wrapper mappings.

The repo needs shared role contracts that are visible in GitHub, easy for any AI client to read, and verifiable without external tooling. Skillshare can help distribute assets, but coupling correctness to the Skillshare CLI would make the harness depend on local sync state instead of committed repository state.

## Decision
Store canonical cross-client agent contracts under `docs/agents/`.

Each logical role from `docs/AI_WORKFLOW.md` has one canonical contract:

- `docs/agents/lead-architect.md`
- `docs/agents/database-advisor.md`
- `docs/agents/step-implementer.md`
- `docs/agents/code-reviewer.md`
- `docs/agents/test-writer.md`
- `docs/agents/debugger.md`
- `docs/agents/refactor-advisor.md`

Root wrappers and tool-specific adapters must reference those contracts:

- `AGENTS.md` maps Codex roles to canonical contracts and Codex execution modes.
- `CLAUDE.md` maps Claude roles to canonical contracts and `.claude/agents/` adapters.
- `GEMINI.md` maps Gemini roles to canonical contracts and Gemini capabilities.
- `.claude/agents/*.md` remain native Claude agent files but explicitly reference their canonical `docs/agents/` contract.

The harness enforces the contract surface with standard-library checks:

- missing canonical contract files are FAIL findings;
- wrappers missing canonical contract paths are FAIL findings;
- Claude adapters missing canonical contract references are FAIL findings.

Skillshare remains optional distribution infrastructure. It may sync or copy adapters in the future, but `docs/agents/` remains the source of truth and the harness must not depend on Skillshare being installed.

## Alternatives Considered
- **Use `.skillshare/extras/agents/` as canonical source:** Rejected because it couples the repository's correctness model to a sync tool. Skillshare can distribute contracts, but it should not own the source of truth.
- **Keep `.claude/agents/` as canonical source:** Rejected because it keeps a Claude-specific path as the shared standard and makes non-Claude clients interpret Claude metadata as policy.
- **Duplicate role behavior in each wrapper:** Rejected because duplicated prompts drift and undermine cross-client portability.

## Consequences
- **Positive:** All AI clients can load the same role contracts from a repo-native docs path.
- **Positive:** Claude keeps native agent support without owning the shared behavior.
- **Positive:** Harness verification now catches role contract drift before implementation work proceeds.
- **Positive:** Skillshare can still be used later for distribution without becoming a hard dependency.
- **Negative:** There is now a small adapter-maintenance burden when a role contract changes.
- **Follow-up:** If future clients add native agent directories, add thin adapters that reference `docs/agents/` and extend the harness only where those adapters become committed repo state.

## References
- `docs/specs/archive/2026-05-01-cross-client-agent-contracts.md`
- `docs/plans/archive/2026-05-01-cross-client-agent-contracts.md`
- `docs/agents/`
- `.claude/agents/`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `scripts/harness/checks.py`
