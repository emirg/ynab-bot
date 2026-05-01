# Spec: Project Instructions Refactoring

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.29 — Project Instructions Refactoring
- **Related ADRs:** docs/adrs/2026-04-30-executable-harness-gates.md
- **Harness Roadmap Marker:** E.29 — Project Instructions Refactoring

## Summary
The repository currently maintains similar project instructions in `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`. This refactor makes `AGENTS.md` the canonical shared instruction file and turns Claude/Gemini entrypoints into thin tool-specific wrappers, with harness checks to prevent future instruction drift.

## Problem
- `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` duplicate workflow, command, source-of-truth, shared-skill, and handoff instructions.
- Duplicated agent instructions can drift when one file is updated and the others are forgotten.
- The command registry exists, but agent entrypoints still contain copied command examples instead of delegating to the canonical command document.

## Goals
- Consolidate shared project rules into `AGENTS.md`.
- Keep `CLAUDE.md` and `GEMINI.md` as thin role-mapping adapters that reference `AGENTS.md`.
- Preserve tool-specific role mappings for Codex, Claude Code, and Gemini CLI.
- Add harness validation that detects wrapper drift and duplicated shared sections.
- Make command instructions flow through the canonical command registry.

## Non-Goals
- Replace `docs/AI_WORKFLOW.md` or `docs/DOCUMENTATION_WORKFLOW.md`.
- Remove Claude or Gemini role mappings.
- Introduce a new agent framework or external dependency.
- Change runtime bot behavior, Railway behavior, or financial invariant logic.

## Users / Consumers
- Codex, Claude Code, Gemini CLI, and any future AI assistant reading project instructions.
- Maintainers reviewing cross-agent workflow behavior.
- The documentation harness, which enforces instruction consistency before deploy.

## Expected Behavior
- `AGENTS.md` contains the shared project instructions that all agents must follow.
- `CLAUDE.md` and `GEMINI.md` instruct their tools to read and follow `AGENTS.md` first.
- `CLAUDE.md` and `GEMINI.md` retain only the `AGENTS.md` pointer and tool-specific role mapping.
- Shared command instructions point to `docs/harness/COMMANDS.md` instead of duplicating command blocks in every agent entrypoint.
- Harness diagnostics fail when wrappers stop referencing `AGENTS.md`, duplicate shared sections, or lose required role mapping.

## Inputs and Outputs
- **Inputs:** Project entrypoint docs: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`; command registry docs; harness checks.
- **Outputs:** Refactored entrypoint docs and harness findings.
- **Public Interfaces:** Agent entrypoint Markdown files and `.venv/bin/python scripts/harness/check_docs.py` / `.venv/bin/python scripts/harness/verify.py --ci`.

## Business Rules and Constraints
- Project workflow remains `SPEC -> PLAN -> IMPLEMENT -> REVIEW -> DONE`.
- All agents must still read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md` before task work.
- YNAB remains the financial source of truth.
- Python commands must still use `.venv` and remain registered in `docs/harness/COMMANDS.md`.
- Harness implementation must use only the Python standard library.

## Edge Cases and Failure Handling
- If a wrapper references `AGENTS.md` but omits role mapping, the harness should fail.
- If a wrapper reintroduces copied shared command blocks or full source-of-truth sections, the harness should fail.
- If `AGENTS.md` stops referencing the workflow docs, command registry, source-of-truth rules, or handoff protocol, the harness should fail.
- Future agent wrappers should be able to follow the same pattern without copying shared sections.

## Acceptance Criteria
- [x] `AGENTS.md` is the canonical shared instruction entrypoint.
- [x] `CLAUDE.md` and `GEMINI.md` are thin role-mapping wrappers that reference `AGENTS.md`.
- [x] Tool-specific role mappings remain present and clear.
- [x] Shared command instructions reference `docs/harness/COMMANDS.md` instead of copied command blocks.
- [x] Harness checks fail on wrapper drift or duplicated shared sections.
- [x] Focused harness tests cover valid wrappers and representative drift failures.
- [x] `ROADMAP.md`, handoff state, and ADR references are updated at closeout.

## Open Questions
- None.

## References
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `docs/AI_WORKFLOW.md`
- `docs/DOCUMENTATION_WORKFLOW.md`
- `docs/harness/COMMANDS.md`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
