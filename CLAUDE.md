# CLAUDE.md

Read and follow `AGENTS.md` first. This file only maps project workflow roles to Claude Code capabilities.

## Role Mapping
When `docs/AI_WORKFLOW.md` refers to a logical role, use the corresponding agent from `.claude/agents/`. Each Claude agent must reference the canonical contract in `docs/agents/`.

| Logical Role | Canonical Contract | Claude Agent |
|---|---|---|
| **Orchestrator** | `docs/agents/orchestrator.md` | Active Claude Code session; dispatches `.claude/agents/` only when the PLAN and session policy allow it |
| **Lead Architect** | `docs/agents/lead-architect.md` | `ynab-lead-architect` |
| **Database Advisor** | `docs/agents/database-advisor.md` | `dba-advisor` |
| **Step Implementer** | `docs/agents/step-implementer.md` | `plan-step-implementer` |
| **Code Reviewer** | `docs/agents/code-reviewer.md` | `code-reviewer` |
| **Test Writer** | `docs/agents/test-writer.md` | `test-writer` |
| **Debugger** | `docs/agents/debugger.md` | `debugger` |
| **Refactor Advisor** | `docs/agents/refactor-advisor.md` | `refactor-advisor` |
