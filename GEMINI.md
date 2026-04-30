# GEMINI.md

You are **Gemini CLI**, an AI assistant working on this project.

## Universal Workflow
**CRITICAL:** Before starting any task, you MUST read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.

- `docs/DOCUMENTATION_WORKFLOW.md` defines when to create SPECs, PLANs, and ADRs.
- `docs/AI_WORKFLOW.md` defines the execution pipeline, architectural invariants, and handoff protocol.

## Role Mapping
When `docs/AI_WORKFLOW.md` refers to a logical role, use the corresponding Gemini skills or tools:

| Logical Role | Gemini Capability |
|---|---|
| **Lead Architect** | Activate `writing-plans` skill |
| **Database Advisor** | Use `codebase_investigator` for schema review |
| **Step Implementer** | Direct tool use (`replace`, `write_file`) |
| **Code Reviewer** | Self-review against invariants in `docs/AI_WORKFLOW.md` |
| **Test Writer** | Activate `Pytest Testing` skill |
| **Debugger** | Use `codebase_investigator` for root cause |
| **Refactor Advisor** | Use `python-design-patterns` skill |

## Commands
All Python commands must be run using the `.venv` virtual environment.

```bash
.venv/bin/python main.py          # Run
.venv/bin/pytest                   # All tests
.venv/bin/pytest tests/test_domain_models.py # File
.venv/bin/pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic # Specific
.venv/bin/pytest -k "test_predict_category" # Keyword filter
```

## Shared Skills
Reusable cross-agent skills live in `.agents/skills/`.

Use them selectively instead of duplicating autoskills summaries in this file. Current shared skills cover testing, Python design patterns, Pydantic, performance, security, code execution, and Railway operations.

## Handoff Protocol
When the user triggers a handoff, generate the exact Markdown content for `docs/wip_state.md` following the strict structure defined in `docs/AI_WORKFLOW.md`. State clearly that the last worker was **Gemini CLI**.
