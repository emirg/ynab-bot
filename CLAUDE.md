# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Context & Rules
- **Project:** YNAB Telegram Bot (Python/SQLite/OpenAI). Spanish UI.
- **Roadmap:** READ `ROADMAP.md` for planned features.
- **Architecture:** READ `docs/ARCHITECTURE.md` for layers, data flow, conventions, and OAuth.
- **YNAB Units:** Amounts are in milliunits (×1000). Negate for expenses.
- **Dependency Injection:** YNAB services use `YNABRepositoryFactory` (per-user, not singleton).

## Session Initialization
At the start of every session, read `docs/wip_state.md` and continue from where the last session left off.

## Plans
- Use `docs/plans/_TEMPLATE.md` for feature planning.
- Save active plans to `docs/plans/`, archive completed ones to `docs/plans/archive/`.

## Orchestration

When the user triggers pipeline work ("implement", "build this", "plan next milestone", or approves a plan), READ `docs/ORCHESTRATION.md` for the full protocol.

Agent definitions live in `.claude/agents/`. **Do not modify agent files** without explicit user approval.

**Quick routing:**

| Situation | Agent |
|---|---|
| Feature plan from roadmap | `ynab-lead-architect` |
| Architectural review | `ynab-lead-architect` |
| DB changes (pre-implementation) | `dba-advisor` |
| Implementing a plan step | `plan-step-implementer` |
| Code review after implementation | `code-reviewer` |
| Missing tests or coverage drop | `test-writer` |
| Test failure during implementation | `debugger` |
| Cleanup / refactor request | `refactor-advisor` |

## Commands
All Python commands use the `.venv` virtual environment.

```bash
.venv/bin/python main.py          # Run
.venv/bin/pytest                   # All tests
.venv/bin/pytest tests/file.py     # Specific file
.venv/bin/pytest -k "keyword"      # Filter
```

## Handoff Protocol
On "prepare handoff", "save state", or approaching rate limit — stop coding and overwrite `docs/wip_state.md`:
- **Last worker:** Claude Code
- **Current Objective:** [1-2 lines, reference active plan if applicable]
- **Last Action:** [Specific]
- **Modified Files:** [List or "None"]
- **Current State / Blocker:** [Exact error or remaining logic]
- **Next Step:** [Exact technical instruction to resume]
