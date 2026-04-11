# GEMINI.md

You are **Gemini CLI**, an AI assistant working on this project.

## Universal Workflow
**CRITICAL:** Before starting any task, you MUST read `docs/AI_WORKFLOW.md`. This file defines the universal pipeline (Plan → Implement → Review → Done), architectural invariants, and handoff protocols that all AI assistants on this project follow.

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
.venv/bin/pytest                   # All tests (~413, ~89% cov)
.venv/bin/pytest tests/test_domain_models.py # File
.venv/bin/pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic # Specific
.venv/bin/pytest -k "test_predict_category" # Keyword filter
```

## Handoff Protocol
When the user triggers a handoff, generate the exact Markdown content for `docs/wip_state.md` following the strict structure defined in `docs/AI_WORKFLOW.md`.
