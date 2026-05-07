# AGENTS.md

This is the canonical shared instruction file for AI assistants working on this project. Tool-specific files such as `CLAUDE.md` and `GEMINI.md` must stay thin wrappers that point here and define only their tool-specific role mapping.

## Universal Workflow
**CRITICAL:** Before starting any task, you MUST read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.

- `docs/DOCUMENTATION_WORKFLOW.md` defines when to create SPECs, PLANs, and ADRs.
- `docs/AI_WORKFLOW.md` defines the execution pipeline, architectural invariants, and handoff protocol.

## Role Mapping
When `docs/AI_WORKFLOW.md` refers to a logical role, each AI tool must use its own wrapper file to map that role to the tool's capabilities.

Codex uses the following internal mode of operation. Before adopting or delegating a role, load the canonical contract listed for that role.

Project preference: use the repo-native multi-agent protocol when useful for approved PLAN work. For Codex, this means spawning subagents for eligible steps only when the current session and client policy permit it; otherwise, adopt the target role locally and preserve the same worker output contract.

| Logical Role | Canonical Contract | Codex Internal Mode |
|---|---|---|
| **Orchestrator** | `docs/agents/orchestrator.md` | Group sequencing, delegation decisions, integration, review routing, and closeout. Uses subagents only when client policy permits. |
| **Lead Architect** | `docs/agents/lead-architect.md` | Analysis of `ROADMAP.md` & `_TEMPLATE.md` based planning. |
| **Database Advisor** | `docs/agents/database-advisor.md` | Schema & migration safety specialist. |
| **Step Implementer** | `docs/agents/step-implementer.md` | Clean code & milliunit invariant enforcement. |
| **Code Reviewer** | `docs/agents/code-reviewer.md` | Self-correction & architectural compliance check. |
| **Test Writer** | `docs/agents/test-writer.md` | `pytest` specialist (Unit & Integration). |
| **Debugger** | `docs/agents/debugger.md` | Root-cause analysis via logs & stack traces. |
| **Refactor Advisor** | `docs/agents/refactor-advisor.md` | Complexity reduction & DRY specialist. |

## Commands
All living command references are centralized in `docs/harness/COMMANDS.md`.

Use the commands from that registry rather than copying command blocks into agent-specific instruction files.

## Source Of Truth
YNAB is the financial source of truth for this project.

- Assume users can create, edit, split, recategorize, and reconcile transactions directly in YNAB outside the bot.
- When YNAB exposes category activity, balances, availability, or transaction structure, prefer that data over local guesses or bot-only history.
- Apply the financial read matrix consistently: spending totals and category rankings come from transactions, budget health comes from category snapshots, and account balances come from account fields.
- Treat `/recent`, `/editar`, and `/deshacer` as workflow conveniences, not authoritative reporting surfaces.
- If a local computation disagrees with YNAB, the implementation should be corrected to reconcile with YNAB.

## Shared Skills
Reusable cross-agent skills live in `.agents/skills/`.

Keep this file concise: do not paste autoskills-generated inventories here. Refer agents to the skill directory and load only the specific `SKILL.md` files needed for the task.

## Shared Agent Contracts
Canonical cross-client agent contracts live in `docs/agents/`, including the Orchestrator delegation contract. Tool-specific agent files and wrappers must reference these contracts instead of becoming independent sources of role behavior.

## Handoff Protocol
When the user triggers a handoff, overwrite `docs/wip_state.md` following the strict structure defined in `docs/AI_WORKFLOW.md`. State clearly that the last worker was **Codex**.
