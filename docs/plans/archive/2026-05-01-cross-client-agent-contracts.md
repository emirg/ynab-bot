# Plan: Cross-Client Agent Contracts

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.30
- **Source Spec:** `docs/specs/archive/2026-05-01-cross-client-agent-contracts.md`
- **Goal:** Make every project AI client use the same role contracts by adding canonical agent specs, thin client mappings, and executable harness checks.
- **Approach:** Introduce shared canonical role files, adapt existing Claude agents to reference them, update root wrapper docs for Codex and Gemini, then extend the existing standard-library harness so cross-client role drift blocks CI.

## Affected Components
- `docs/agents/` — canonical role contract files and the source of truth for shared role behavior.
- `.claude/agents/*.md` — Claude-native adapters that preserve current Claude functionality while referencing canonical contracts.
- `AGENTS.md` — Codex wrapper mapping from logical roles to canonical contracts and Codex execution behavior.
- `CLAUDE.md` — Claude wrapper mapping from logical roles to canonical contracts and `.claude/agents/` adapters.
- `GEMINI.md` — Gemini wrapper mapping from logical roles to canonical contracts and Gemini execution behavior.
- `.skillshare/config.yaml` — optional future distribution configuration only if adapters are later synced through Skillshare.
- `scripts/harness/checks.py` — cross-client agent contract checks.
- `tests/harness/test_checks.py` — focused harness unit tests.
- `tests/harness/test_repository_docs.py` — repository-state verification.
- `docs/adrs/` — ADR for canonical agent contract location and adapter policy if finalized during implementation.
- `docs/harness/COMMANDS.md` — only if a new advisory command is added; otherwise no change.

## Prerequisites (Manual)
- [x] Canonical contract location selected: `docs/agents/`.
- [x] Decide initial drift severity for `.claude/agents/` adapters:
  - Recommended: CI failure when an adapter is missing its canonical reference; warning for deeper content differences in the first slice.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Establish failing tests before changing role files. -->

#### [x] Step 1: Add harness tests for canonical role contracts
- **Files:** `tests/harness/test_checks.py`
- **Action:** Add tests that construct temporary repos with `docs/AI_WORKFLOW.md`, wrapper docs, `docs/agents/` canonical files, and Claude adapters. Cover PASS when all roles are present and FAIL when a logical role lacks a canonical contract.
- **Tests:** `.venv/bin/pytest tests/harness/test_checks.py -q`

#### [x] Step 2: Add harness tests for wrapper mappings
- **Files:** `tests/harness/test_checks.py`
- **Action:** Add tests that fail when `AGENTS.md`, `CLAUDE.md`, or `GEMINI.md` omits a logical role or omits the canonical contract path for that role.
- **Tests:** `.venv/bin/pytest tests/harness/test_checks.py -q`

#### [x] Step 3: Add repository-state test for checked-in contracts
- **Files:** `tests/harness/test_repository_docs.py`
- **Action:** Add a repository-level test that expects the real checkout to pass the new cross-client agent checks after implementation.
- **Tests:** `.venv/bin/pytest tests/harness/test_repository_docs.py -q`

### Group 2 (depends on: Group 1)
<!-- Implement reusable checks without changing repo docs yet. -->

#### [x] Step 4: Implement logical role contract discovery
- **Files:** `scripts/harness/checks.py`
- **Action:** Add standard-library helpers that derive the logical roles from `LOGICAL_ROLES`, locate `docs/agents/`, and map role names to expected slugs.
- **Tests:** `.venv/bin/pytest tests/harness/test_checks.py -q`

#### [x] Step 5: Implement wrapper and adapter checks
- **Files:** `scripts/harness/checks.py`
- **Action:** Add findings for missing canonical contracts, missing role mappings in `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, and Claude adapters that do not reference the canonical contract.
- **Tests:** `.venv/bin/pytest tests/harness/test_checks.py -q`

### Group 3 (depends on: Group 2)
<!-- Add shared contracts and adapt clients. -->

#### [x] Step 6: Create canonical agent contract files
- **Files:** `docs/agents/lead-architect.md`, `docs/agents/database-advisor.md`, `docs/agents/step-implementer.md`, `docs/agents/code-reviewer.md`, `docs/agents/test-writer.md`, `docs/agents/debugger.md`, `docs/agents/refactor-advisor.md`
- **Action:** Create one markdown file per logical role. Preserve current Claude role behavior where useful, but remove Claude-only assumptions from the canonical contract body.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`

#### [x] Step 7: Refresh Claude agent adapters
- **Files:** `.claude/agents/code-reviewer.md`, `.claude/agents/dba-advisor.md`, `.claude/agents/debugger.md`, `.claude/agents/plan-step-implementer.md`, `.claude/agents/refactor-advisor.md`, `.claude/agents/test-writer.md`, `.claude/agents/ynab-lead-architect.md`
- **Action:** Keep Claude frontmatter and native agent names, but add a clear canonical-contract reference and remove duplicated behavior only when it is safely represented by the canonical file.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`

#### [x] Step 8: Refresh root client wrappers
- **Files:** `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- **Action:** Update each role mapping so it names both the canonical contract and the client-specific execution mechanism. Keep wrappers thin and avoid duplicating full contract text.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`

#### [x] Step 9: Document Skillshare as optional distribution
- **Files:** `.skillshare/config.yaml`, `docs/adrs/2026-05-01-cross-client-agent-contracts.md`
- **Action:** Do not make Skillshare part of the correctness path. If adapter syncing through Skillshare is useful later, document it as optional distribution that must preserve `docs/agents/` as the canonical source.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`

### Group 4 (depends on: Group 3)
<!-- Record the long-lived policy if the implementation settles the open questions. -->

#### [x] Step 10: Write ADR for canonical agent contracts
- **Files:** `docs/adrs/2026-05-01-cross-client-agent-contracts.md`
- **Action:** Record `docs/agents/` as the canonical location, the adapter policy, Skillshare's optional role, and consequences for future clients.
- **Tests:** `.venv/bin/python scripts/harness/check_docs.py`

### Group 5 (depends on: Group 4)
<!-- Final verification and lifecycle closeout. -->

#### [x] Step 11: Run focused and CI verification
- **Files:** no edits expected
- **Action:** Run focused harness tests, advisory diagnostics, and CI-equivalent harness verification.
- **Tests:** `.venv/bin/pytest tests/harness -q`; `.venv/bin/python scripts/harness/check_docs.py`; `.venv/bin/python scripts/harness/verify.py --ci`

#### [x] Step 12: Review and archive completed docs
- **Files:** `docs/specs/2026-05-01-cross-client-agent-contracts.md`, `docs/plans/2026-05-01-cross-client-agent-contracts.md`, `docs/specs/archive/`, `docs/plans/archive/`, `docs/wip_state.md`
- **Action:** After implementation passes review, update statuses, archive the SPEC and PLAN, update ADR references to archived paths, and refresh handoff state with Codex as the last worker.
- **Tests:** `.venv/bin/python scripts/harness/verify.py --ci`; `.venv/bin/pytest`

## Constraints & Architecture
- Keep `docs/AI_WORKFLOW.md` as the source of truth for logical role names.
- Keep client wrappers thin; shared role behavior belongs in canonical contract files.
- Store canonical role contracts in `docs/agents/`; do not couple correctness to Skillshare or any other sync CLI.
- Use only Python standard-library code in `scripts/harness/`.
- Preserve Claude native agent support.
- If an AI client lacks native subagents, it must adopt the role using the canonical contract instead of skipping the role.
- Do not edit runtime bot behavior, persistence, or YNAB integration in this feature.

## Verification
- [x] `.venv/bin/pytest tests/harness/test_checks.py -q`
- [x] `.venv/bin/pytest tests/harness/test_repository_docs.py -q`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci`
- [x] `.venv/bin/pytest`
