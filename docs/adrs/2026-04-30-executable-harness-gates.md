# ADR: Executable Harness Gates

## Metadata
- **Status:** Accepted
- **Date:** 2026-04-30
- **Related Spec:** `docs/specs/archive/2026-04-30-executable-harness-gates.md`
- **Related Plan:** `docs/plans/archive/2026-04-30-executable-harness-gates.md`
- **Supersedes:** None
- **Superseded By:** None

## Context
The repository relies on a documented SPEC, PLAN, IMPLEMENT, REVIEW, DONE workflow, but that workflow was previously enforced only by human or agent discipline. Completed documents could remain active, ADR references could drift, and stale agent instructions could point future workers at retired workflow context.

Railway is the current deploy enforcement surface. A lightweight gate is needed before pytest runs so documentation workflow violations fail early without adding external dependencies or delaying a later OpenSpec/OpenSDD evaluation.

## Decision
Use standard-library Python harness checks as the first enforcement layer:

- `scripts/harness/check_docs.py` provides advisory local diagnostics and exits zero by default.
- `scripts/harness/verify.py --ci` provides blocking CI verification and exits nonzero on FAIL findings.
- Railway runs `python scripts/harness/verify.py --ci && pytest` after dependency installation.

The initial gate validates documentation workflow coherence only: required workflow files/templates, active SPEC/PLAN status and source links, ADR doc references, agent entrypoint workflow references, and stale legacy workflow references.

The second harness slice extends the same decision with machine-readable JSON output and explicit ROADMAP coherence metadata. Implemented archived SPECs and completed archived PLANs must now declare a `Harness Roadmap Marker` that appears in `ROADMAP.md`, and completed archived PLANs must have all task checkboxes checked unless a historical document is explicitly ignored by harness metadata.

The Railway config harness slice extends the enforcement layer to the deploy configuration itself. The harness parses `railway.toml` with the Python standard library, verifies that the build command runs `python scripts/harness/verify.py --ci` before `pytest`, and confirms the deploy start command remains `python main.py`.

The command registry slice centralizes living local and Railway commands in `scripts/harness/commands.py` and `docs/harness/COMMANDS.md`. The harness now validates that agent entrypoints and workflow docs reference the canonical commands instead of maintaining independent copies.

The runtime financial invariant slice extends the same enforcement surface from process safety into product correctness evidence. The harness now checks that docs, source, and tests still preserve the financial read matrix: milliunit expense conversion, transaction-backed spending totals, category-snapshot budget health, account-field balances, and the recent/edit/undo convenience boundary. A direct advisory command, `scripts/harness/check_financial_invariants.py`, exposes those checks without running the full documentation harness.

## Alternatives Considered
- **Adopt OpenSpec/OpenSDD immediately:** Deferred because the immediate risk is local documentation drift, and adding a new framework should be evaluated as a separate feature.
- **Rely on pytest only:** Rejected because pytest does not validate documentation lifecycle state or agent instruction drift.
- **Use shell scripts:** Rejected because Python provides more maintainable parsing, clearer tests, and cross-platform behavior while still using only the standard library.

## Consequences
- **Positive:** Documentation drift now has a deterministic local and CI signal before deploy tests run.
- **Positive:** The gate is dependency-free and can run before application imports or external service setup.
- **Positive:** Deploy configuration drift now fails in the same local and CI harness surface as documentation drift.
- **Positive:** Local, agent, and Railway command references now share one registry-backed source of truth.
- **Positive:** Financial invariant drift now has a deterministic local and CI signal before deploy tests run.
- **Negative:** The gate still does not enforce linting, typing, or broad coverage thresholds.
- **Follow-up:** Continue expanding invariant checks only where they protect high-risk financial behavior.

## References
- `docs/specs/archive/2026-04-30-executable-harness-gates.md`
- `docs/plans/archive/2026-04-30-executable-harness-gates.md`
- `docs/specs/archive/2026-04-30-harness-roadmap-coherence.md`
- `docs/plans/archive/2026-04-30-harness-roadmap-coherence.md`
- `docs/specs/archive/2026-04-30-railway-config-harness.md`
- `docs/plans/archive/2026-04-30-railway-config-harness.md`
- `docs/specs/archive/2026-04-30-harness-command-registry.md`
- `docs/plans/archive/2026-04-30-harness-command-registry.md`
- `docs/specs/archive/2026-05-01-runtime-financial-invariant-harness.md`
- `docs/plans/archive/2026-05-01-runtime-financial-invariant-harness.md`
- `scripts/harness/checks.py`
- `scripts/harness/check_financial_invariants.py`
- `scripts/harness/commands.py`
- `docs/harness/COMMANDS.md`
- `railway.toml`
