# GEMINI.md

Read and follow `AGENTS.md` first. This file only maps project workflow roles to Gemini CLI capabilities.

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
