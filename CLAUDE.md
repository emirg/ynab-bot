# CLAUDE.md

You are **Claude Code**, an AI assistant working on this project.

## Universal Workflow
**CRITICAL:** Before starting any task, you MUST read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.

- `docs/DOCUMENTATION_WORKFLOW.md` defines when to create SPECs, PLANs, and ADRs.
- `docs/AI_WORKFLOW.md` defines the execution pipeline, architectural invariants, and handoff protocol.

## Role Mapping
When `docs/AI_WORKFLOW.md` refers to a logical role, use the corresponding agent from `.claude/agents/`:

| Logical Role | Claude Agent |
|---|---|
| **Lead Architect** | `ynab-lead-architect` |
| **Database Advisor** | `dba-advisor` |
| **Step Implementer** | `plan-step-implementer` |
| **Code Reviewer** | `code-reviewer` |
| **Test Writer** | `test-writer` |
| **Debugger** | `debugger` |
| **Refactor Advisor** | `refactor-advisor` |

## Commands
All Python commands must be run using the `.venv` virtual environment.

```bash
.venv/bin/python main.py          # Run
.venv/bin/pytest                   # All tests
.venv/bin/pytest tests/file.py     # Specific file
.venv/bin/pytest -k "keyword"      # Filter
```

## Shared Skills
Reusable cross-agent skills live in `.agents/skills/`.

Keep this file focused on workflow and role mapping. Do not commit large autoskills-generated summaries here; load the relevant `SKILL.md` files directly when a task calls for them.

## Handoff Protocol
When the user triggers a handoff, overwrite `docs/wip_state.md` following the strict structure defined in `docs/AI_WORKFLOW.md`. State clearly that the last worker was **Claude Code**.
