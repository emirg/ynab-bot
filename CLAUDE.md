# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Context & Rules
- **Project:** YNAB Telegram Bot (Python/SQLite/OpenAI). Spanish UI.
- **Roadmap:** READ `ROADMAP.md` to know what things are planned for future implementations.
- **Deep Architecture:** For deep architecture, data flow, conventions, or OAuth details, READ `docs/ARCHITECTURE.md`.
- **YNAB Units:** YNAB amounts are in milliunits (×1000). Negate for expenses.
- **Dependency Injection:** YNAB services use `YNABRepositoryFactory` (not a singleton repo). Resolve per-user.

## Session Initialization
Whenever you start a new session or the user asks to "resume", your VERY FIRST action MUST be to read `docs/wip_state.md`.
- If it indicates Gemini completed a task, acknowledge it and continue.
- If it indicates Gemini didn't complete it, or if the file has your last handoff, or if it's empty/missing: continue from where you left off.

## Plans
- Use `docs/plans/_TEMPLATE.md` for feature planning. Break down into atomic, sequential steps with exact file paths (implementation + tests).
- Save active plans to `docs/plans/` and reference them here.
- Move finished plans to `docs/plans/archive/` and update references.

## Orchestration

The main session (you) is the orchestrator. Subagents cannot call other subagents — only you can delegate via the Agent tool.

When the user triggers pipeline work ("implement", "build this", "plan next milestone", or approves a plan), READ `docs/ORCHESTRATION.md` for the full pipeline protocol, delegation templates, and execution rules.

## Subagents

Agent definitions live in `.claude/agents/` (project-level, tracked in Git). **Do not modify agent files** during implementation work — changes require explicit user approval.

| Agent | Role | Mode |
|---|---|---|
| `ynab-lead-architect` | Planning, architectural review, design decisions | Opus, R/O (docs only) |
| `dba-advisor` | Database schema, queries, migrations, performance | Sonnet, R/O |
| `plan-step-implementer` | Executes individual plan steps | Sonnet, R/W |
| `code-reviewer` | Post-implementation code review | Sonnet, R/O |
| `test-writer` | Writes and fixes pytest tests | Sonnet, R/W |
| `debugger` | Root cause analysis, minimal bug fixes | Sonnet, R/W |
| `refactor-advisor` | Analyzes code smells, proposes refactoring plans | Sonnet, R/O |

**Quick routing** (for full delegation templates, see `docs/ORCHESTRATION.md`):

| Situation | Agent |
|---|---|
| Need a feature plan from the roadmap | `ynab-lead-architect` |
| Architectural review of a completed feature | `ynab-lead-architect` |
| Plan involves DB changes (pre-implementation) | `dba-advisor` |
| Implementing a plan step | `plan-step-implementer` |
| All groups complete, need code review | `code-reviewer` |
| Coverage dropped or tests missing | `test-writer` |
| A test fails during implementation | `debugger` |
| User asks to clean up / refactor | `refactor-advisor` → then convert proposal to plan |

## Commands
All Python commands must be run using the `.venv` virtual environment.

```bash
# Setup (one-time)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
.venv/bin/python main.py

# Tests
.venv/bin/pytest # All tests (~458, ~88% cov)
.venv/bin/pytest tests/test_domain_models.py # File
.venv/bin/pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic # Specific
.venv/bin/pytest -k "test_predict_category" # Keyword filter
```

## Handoff Protocol
If you receive the explicit command "prepare handoff", "save state", or approach the rate limit, STOP writing new code.
Overwrite `docs/wip_state.md` strictly using this structure:
- Make clear Claude Code was the last one to work.
- **Current Objective:** [1 or 2 lines describing the feature/bug. Reference active plan if applicable and progress]
- **Last Action:** [Specific last action taken]
- **Modified Files:** [List of unsaved paths or "None"]
- **Current State / Blocker:** [Exact error, exception, or logic left to complete]
- **Next Step:** [Exact technical instruction for the next AI to resume]