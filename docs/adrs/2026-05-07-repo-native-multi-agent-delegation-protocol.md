# ADR: Repo-Native Multi-Agent Delegation Protocol

## Metadata
- **Status:** Accepted
- **Date:** 2026-05-07
- **Related Spec:** `docs/specs/archive/2026-05-07-repo-native-multi-agent-delegation-protocol.md`
- **Related Plan:** `docs/plans/archive/2026-05-07-repo-native-multi-agent-delegation-protocol.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The repository already uses a structured AI workflow with SPEC, PLAN, ADR, review, archive, and handoff rules. It also has canonical cross-client role contracts under `docs/agents/` and thin wrappers for Claude, Gemini, and Codex. Those pieces make single-agent role adoption reasonably deterministic, but they do not fully define reliable multi-agent delegation.

Plans currently group steps so independent work can run in parallel, but the group structure is not enough for safe automated delegation. The Orchestrator still needs explicit rules for spawn criteria, write ownership, worker outputs, failure routing, and final integration. External tools such as Ruflo or Claude Flow could add orchestration features, but they would introduce another source of workflow truth and likely center Claude-specific conventions.

## Decision
Adopt a repo-native multi-agent delegation protocol.

The repository will define delegation behavior in committed, tool-neutral docs and enforce the highest-value safety rules through the existing standard-library harness. The protocol will live alongside the existing agent-contract system:

- `docs/agents/orchestrator.md` will define the canonical Orchestrator and delegation contract.
- `docs/AI_WORKFLOW.md` will describe when delegation is allowed and how the active Orchestrator integrates worker results.
- `docs/plans/_TEMPLATE.md` will require delegation metadata on plan steps, including role, write scope, read scope, dependencies, verification, and escalation target.
- `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` will stay thin and map client-specific behavior back to the canonical contract.
- `scripts/harness/checks.py` will validate active plan metadata and parallel write-scope safety.

Delegation is a capability, not an obligation. A client may use subagents only when the client policy permits it and the active PLAN proves the work is safe to split. A client without native subagents must adopt the relevant role locally.

## Alternatives Considered
- **Use Ruflo or Claude Flow as the workflow owner:** Rejected because the repository already has a strong SPEC/PLAN/ADR and harness model. Making an external orchestration tool the correctness path would duplicate governance and likely bias the repo toward Claude-specific files.
- **Keep the current prose-only parallel group rules:** Rejected because prose grouping helps humans but does not give agents enough structure to make safe default delegation decisions.
- **Allow assistants to decide delegation ad hoc:** Rejected because it makes parallel work dependent on the active client and increases the chance of overlapping edits or skipped verification.
- **Require all clients to use subagents:** Rejected because client capabilities differ. The repo should define the contract while allowing clients to delegate, adopt roles locally, or ask for permission according to their platform constraints.

## Consequences
- **Positive:** Multi-agent execution becomes a repo-defined workflow rather than a Claude-specific habit.
- **Positive:** Plans become easier for agents and humans to review for safe parallelism.
- **Positive:** Harness checks can catch unsafe write-scope overlap before implementation starts.
- **Positive:** Codex, Claude, Gemini, and future clients can share the same delegation expectations.
- **Negative:** Plans will require more metadata, which adds drafting overhead.
- **Negative:** Harness parsing must stay intentionally simple unless a structured plan format is adopted later.
- **Negative:** Repo policy still cannot override client-level permission restrictions for spawning subagents.
- **Follow-up:** Revisit the metadata schema only if future plans need structure that Markdown fields cannot express cleanly.

## References
- `docs/specs/archive/2026-05-07-repo-native-multi-agent-delegation-protocol.md`
- `docs/plans/archive/2026-05-07-repo-native-multi-agent-delegation-protocol.md`
- `docs/adrs/2026-05-01-cross-client-agent-contracts.md`
- `docs/AI_WORKFLOW.md`
- `docs/DOCUMENTATION_WORKFLOW.md`
- `docs/agents/`
- `scripts/harness/checks.py`
