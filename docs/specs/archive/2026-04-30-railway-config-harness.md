# Spec: Railway Config Harness

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** E.19
- **Harness Roadmap Marker:** E.19
- **Related ADRs:** `docs/adrs/2026-04-30-executable-harness-gates.md`

## Summary
The repository harness should validate the Railway deploy configuration before deploy builds rely on it. The check keeps the current standard-library-only approach and catches drift in `railway.toml`, especially build ordering that could skip or reorder the blocking harness gate.

## Problem
- Railway is the deploy enforcement surface, but the harness currently only validates documentation workflow state.
- A future edit to `railway.toml` could remove `verify.py --ci`, run `pytest` first, or change the runtime entrypoint without any local harness signal.

## Goals
- Validate that `railway.toml` exists and is parseable with standard-library Python.
- Validate that Railway build config runs `python scripts/harness/verify.py --ci` before `pytest`.
- Validate that the deploy start command points at `python main.py`.
- Keep diagnostics in the existing `PASS` / `WARN` / `FAIL` finding model and JSON output.

## Non-Goals
- Do not call the Railway CLI or inspect live Railway infrastructure.
- Do not run pytest from `scripts/harness/verify.py`.
- Do not add a third-party TOML parser.
- Do not validate every Railway setting or environment variable in this slice.

## Users / Consumers
- Maintainers and AI agents running local harness diagnostics.
- Railway deploy builds that run `scripts/harness/verify.py --ci`.

## Expected Behavior
- Advisory checks report Railway config findings through `scripts/harness/check_docs.py`.
- CI checks fail when `railway.toml` is missing, malformed, lacks the blocking harness command, runs pytest before the harness, or changes the expected start command.
- Valid current Railway config passes without warnings.

## Inputs and Outputs
- **Inputs:** `railway.toml`.
- **Outputs:** Harness findings in text or JSON.
- **Public Interfaces:** Existing `scripts/harness/check_docs.py` and `scripts/harness/verify.py --ci`.

## Business Rules and Constraints
- The implementation must use only the Python standard library.
- Railway config checks must run as part of the existing `run_checks()` aggregate.
- Build command validation must be order-aware: harness verification before pytest.

## Edge Cases and Failure Handling
- Missing `railway.toml` is a FAIL.
- Malformed TOML is a FAIL with the parse error included.
- Missing `[build].buildCommand` or `[deploy].startCommand` is a FAIL.
- Missing required command segments or wrong command order is a FAIL.

## Acceptance Criteria
- [x] Harness tests cover missing, malformed, valid, missing-harness, wrong-order, and wrong-start-command Railway config cases.
- [x] Checked-in repository docs and Railway config pass `scripts/harness/verify.py --ci`.
- [x] `ROADMAP.md` records the completed harness feature.
- [x] The executable harness ADR references this follow-up slice.

## Open Questions
- None.

## References
- `railway.toml`
- `scripts/harness/checks.py`
- `docs/adrs/2026-04-30-executable-harness-gates.md`
