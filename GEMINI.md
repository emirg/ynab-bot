# GEMINI.md

You are acting as the secondary/fallback AI assistant for this repository. 
The primary system architecture, conventions, and rules are maintained by Claude Code.

## Primary Directives
1. **CRITICAL:** Before answering any architectural or coding question, you MUST read the `CLAUDE.md` file in the root directory to understand the project context, layered architecture, and testing conventions.
2. **Respect the Plans:** If you are asked to implement code, check if there is an active plan in `docs/plans/` and follow it strictly.
3. **Do not modify CLAUDE.md:** Leave the maintenance of the core system prompt to Claude, unless the user explicitly asks you to update it.

## Reverse Handoff Protocol (Back to Claude)
When the user explicitly tells you to "prepare handoff", "prepare handoff back to Claude", or "wrap up for Claude", you MUST generate the exact Markdown content to update the state file. 
Do not output conversational text, ONLY output the Markdown block using this strict structure:
- Make clear you (Gemini CLI) were the last one to work on the code.
- **State:** Returning control to Claude Code.
- **Accomplished by Gemini:** [Specific details of what we just fixed, coded, and committed. Mention exact files].
- **Active Plan Status:** [Which step of the `docs/plans/` was just completed].
- **Next Action for Claude:** [The exact next step Claude must execute upon waking up].