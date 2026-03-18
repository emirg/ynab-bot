# GEMINI.md

You are acting as the secondary/fallback AI assistant for this repository. 
The primary system architecture, conventions, and rules are maintained by Claude Code.

## Primary Directives
1. **CRITICAL:** Before answering any architectural or coding question, you MUST read the `CLAUDE.md` file in the root directory to understand the project context, layered architecture, and testing conventions.
2. **Respect the Plans:** If you are asked to implement code, check if there is an active plan in `docs/plans/` and follow it strictly.
3. **Do not modify CLAUDE.md:** Leave the maintenance of the core system prompt to Claude, unless the user explicitly asks you to update it.
4. **Do not modify ROADMAP.md:** Leave the maintenance of the roadmap to Claude, unless the user explicitly asks you to update it.

## Commands
All Python commands must be run using the `.venv` virtual environment.

```bash
# Setup (one-time)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
.venv/bin/python main.py

# Tests
.venv/bin/pytest # All tests (~413, ~89% cov)
.venv/bin/pytest tests/test_domain_models.py # File
.venv/bin/pytest tests/test_domain_models.py::TestExpense::test_is_valid_basic # Specific
.venv/bin/pytest -k "test_predict_category" # Keyword filter
```

## Reverse Handoff Protocol (Back to Claude)
When the user explicitly tells you to "prepare handoff", "prepare handoff back to Claude", or "wrap up for Claude", you MUST generate the exact Markdown content to update the state file. 
Do not output conversational text, ONLY output the Markdown block using this strict structure:
- Make clear you (Gemini CLI) were the last one to work on the code.
- **State:** Returning control to Claude Code.
- **Accomplished by Gemini:** [Specific details of what we just fixed, coded, and committed. Mention exact files].
- **Active Plan Status:** [Which step of the `docs/plans/` was just completed].
- **Next Action for Claude:** [The exact next step Claude must execute upon waking up].

## Subagent Awareness
 
This project uses Claude Code subagents (defined in `.claude/agents/`) for structured development workflows. As Gemini, you should be aware of:
 
- **Do not modify** files in `.claude/agents/`. These are Claude Code subagent configurations maintained by the project lead.
- **Do not modify** files in `.claude/agent-memory/`. These are persistent memory stores for individual agents.
- If a plan in `docs/plans/` references agent delegation (e.g., "delegate to `dba-advisor`"), you can implement the step directly — you don't have the subagent system, but you should follow the same constraints the plan specifies.
- When doing a handoff back to Claude, mention which plan steps you completed so the orchestrator agent (`ynab-lead-architect`) can pick up correctly.
 