# CLAUDE.md

You are **Claude Code**, an AI assistant working on this project.

## Universal Workflow
**CRITICAL:** Before starting any task, you MUST read `docs/AI_WORKFLOW.md`. This file defines the universal pipeline (Plan → Implement → Review → Done), architectural invariants, and handoff protocols that all AI assistants on this project follow.

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

## Handoff Protocol
When the user triggers a handoff, overwrite `docs/wip_state.md` following the strict structure defined in `docs/AI_WORKFLOW.md`.
