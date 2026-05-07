# GEMINI.md

Read and follow `AGENTS.md` first. This file only maps project workflow roles to Gemini CLI capabilities.

## Role Mapping
When `docs/AI_WORKFLOW.md` refers to a logical role, read the canonical contract in `docs/agents/` and then use the corresponding Gemini skills or tools:

| Logical Role | Canonical Contract | Gemini Capability |
|---|---|---|
| **Orchestrator** | `docs/agents/orchestrator.md` | Active Gemini CLI session; adopt roles locally unless native delegation is available and allowed |
| **Lead Architect** | `docs/agents/lead-architect.md` | Activate `writing-plans` skill |
| **Database Advisor** | `docs/agents/database-advisor.md` | Use `codebase_investigator` for schema review |
| **Step Implementer** | `docs/agents/step-implementer.md` | Direct tool use (`replace`, `write_file`) |
| **Code Reviewer** | `docs/agents/code-reviewer.md` | Self-review against invariants in `docs/AI_WORKFLOW.md` |
| **Test Writer** | `docs/agents/test-writer.md` | Activate `Pytest Testing` skill |
| **Debugger** | `docs/agents/debugger.md` | Use `codebase_investigator` for root cause |
| **Refactor Advisor** | `docs/agents/refactor-advisor.md` | Use `python-design-patterns` skill |
