# Spec: Harness Command Registry

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.20
- **Harness Roadmap Marker:** E.20
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`

## Summary
The executable harness should own the canonical local and CI commands used by humans, agents, and Railway. This slice adds a command registry and validates that living documentation/configuration surfaces reference those commands consistently.

## Problem
- Commands are currently repeated across agent entrypoints, workflow docs, ADRs, architecture docs, and `railway.toml`.
- A future edit can easily leave local instructions saying one thing while Railway or the harness runs another.
- Archived historical plans include old command examples, so the check must focus on current operational surfaces rather than rewriting history.

## Goals
- Add one repo-local command registry for canonical harness, test, run, and Railway commands.
- Add a living command reference document generated from or validated against that registry.
- Validate that root agent entrypoints and workflow docs mention the relevant canonical commands.
- Keep Railway command validation based on the same registry constants.

## Non-Goals
- Do not rewrite archived historical plans that mention older command forms.
- Do not run any registered command from the registry.
- Do not introduce external dependencies or a generation step.
- Do not validate every command in developer docs outside the harness/deploy workflow.

## Users / Consumers
- Maintainers running local checks.
- AI agents following project command instructions.
- Railway deploy builds.

## Expected Behavior
- `scripts/harness/check_docs.py` reports whether the command registry doc exists and contains each canonical command.
- `scripts/harness/verify.py --ci` fails if living docs/configs drift from the registry.
- Valid current docs/configuration pass without warnings.

## Inputs and Outputs
- **Inputs:** `scripts/harness/commands.py`, `docs/harness/COMMANDS.md`, root agent docs, workflow docs, `railway.toml`.
- **Outputs:** Existing harness findings in text or JSON.
- **Public Interfaces:** Existing harness CLIs only.

## Business Rules and Constraints
- The registry and checks must use only Python standard-library modules.
- Agent docs must continue to tell agents to use `.venv` for local Python commands.
- Railway must continue using non-venv commands appropriate for deploy builds.

## Edge Cases and Failure Handling
- Missing command registry documentation is a FAIL.
- A missing canonical command in the registry doc is a FAIL.
- Root agent docs missing run/test commands are FAILs.
- Workflow docs missing local harness/CI harness command references are FAILs.

## Acceptance Criteria
- [x] Tests cover valid command registry references and missing command references.
- [x] Railway checks consume the same registry constants used by command-reference checks.
- [x] Current repository passes the command registry harness.
- [x] `ROADMAP.md` records the completed E.20 feature.
- [x] The executable harness ADR references this slice.

## Open Questions
- None.

## References
- `scripts/harness/checks.py`
- `railway.toml`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
