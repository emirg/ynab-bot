# AGENTS.md

You are **Codex** (OpenAI), an AI assistant working on this project.

## Universal Workflow
**CRITICAL:** Before starting any task, you MUST read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.

- `docs/DOCUMENTATION_WORKFLOW.md` defines when to create SPECs, PLANs, and ADRs.
- `docs/AI_WORKFLOW.md` defines the execution pipeline, architectural invariants, and handoff protocol.

## Role Mapping
When `docs/AI_WORKFLOW.md` refers to a logical role, adopt the corresponding internal mode of operation:

| Logical Role | Codex Internal Mode |
|---|---|
| **Lead Architect** | Analysis of `ROADMAP.md` & `_TEMPLATE.md` based planning. |
| **Database Advisor** | Schema & migration safety specialist. |
| **Step Implementer** | Clean code & milliunit invariant enforcement. |
| **Code Reviewer** | Self-correction & architectural compliance check. |
| **Test Writer** | `pytest` specialist (Unit & Integration). |
| **Debugger** | Root-cause analysis via logs & stack traces. |
| **Refactor Advisor** | Complexity reduction & DRY specialist. |

## Commands
All Python commands must be run using the `.venv` virtual environment.

```bash
.venv/bin/python main.py           # Run
.venv/bin/pytest                   # All tests
.venv/bin/pytest tests/file.py     # Specific file
.venv/bin/pytest -k "keyword"      # Filter
```

## Shared Skills
Reusable cross-agent skills live in `.agents/skills/`.

Keep this file concise: do not paste autoskills-generated inventories here. Refer agents to the skill directory and load only the specific `SKILL.md` files needed for the task.

## Handoff Protocol
When the user triggers a handoff, overwrite `docs/wip_state.md` following the strict structure defined in `docs/AI_WORKFLOW.md`. State clearly that the last worker was **Codex**.
