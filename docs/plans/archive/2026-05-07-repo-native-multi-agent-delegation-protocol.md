# Plan: Repo-Native Multi-Agent Delegation Protocol

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-05-07-repo-native-multi-agent-delegation-protocol.md`
- **Harness Roadmap Marker:** E.30.1 — Repo-Native Multi-Agent Delegation Protocol
- **Goal:** Add a safe, repo-native protocol for when AI clients may delegate plan work to subagents and how that delegation is verified.
- **Approach:** Define the contract first, update workflow and plan metadata around it, then add standard-library harness checks and focused tests.

## Affected Components
- `docs/agents/orchestrator.md` — new canonical delegation and orchestration contract.
- `docs/AI_WORKFLOW.md` — clarify delegation policy, group integration, and client permission boundaries.
- `docs/plans/_TEMPLATE.md` — add delegation metadata to plan steps.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` — map delegation behavior through the canonical contract.
- `scripts/harness/checks.py` — validate active plan delegation metadata and parallel write-scope safety.
- `tests/harness/test_checks.py` — focused checks for safe and unsafe delegation metadata.
- `tests/harness/test_repository_docs.py` — repository-state coverage for the checked-in docs.
- `docs/adrs/2026-05-07-repo-native-multi-agent-delegation-protocol.md` — decision record for repo-native delegation.
- `docs/wip_state.md` — handoff state after implementation or pause.

## Prerequisites (Manual)
- [x] User approved proceeding from the multi-agent workflow assessment to SPEC, PLAN, and ADR.
- [x] User approves this PLAN before implementation changes begin.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Lock the delegation contract before changing templates or harness behavior. -->

#### [x] Step 1: Add canonical Orchestrator contract
- **Role:** Lead Architect
- **Files:** `docs/agents/orchestrator.md`
- **Write Scope:** `docs/agents/orchestrator.md`
- **Read Scope:** `docs/AI_WORKFLOW.md`, `docs/agents/*.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- **Depends On:** None
- **Auto-Delegable:** no
- **Escalation Target:** Lead Architect
- **Action:** Define spawn criteria, local role adoption fallback, group sequencing, file ownership, worker output format, failure routing, and final integration responsibilities.
- **Verification:** `.venv/bin/python scripts/harness/check_docs.py`

#### [x] Step 2: Update workflow delegation rules
- **Role:** Lead Architect
- **Files:** `docs/AI_WORKFLOW.md`
- **Write Scope:** `docs/AI_WORKFLOW.md`
- **Read Scope:** `docs/agents/orchestrator.md`, `docs/DOCUMENTATION_WORKFLOW.md`
- **Depends On:** Step 1
- **Auto-Delegable:** no
- **Escalation Target:** Lead Architect
- **Action:** Add concise delegation rules to the implementation pipeline, including client permission limits and the rule that the active Orchestrator owns integration even when workers run in parallel.
- **Verification:** `.venv/bin/python scripts/harness/check_docs.py`

### Group 2 (depends on: Group 1)
<!-- Make future plans delegation-safe by construction. -->

#### [x] Step 3: Extend plan template metadata
- **Role:** Lead Architect
- **Files:** `docs/plans/_TEMPLATE.md`
- **Write Scope:** `docs/plans/_TEMPLATE.md`
- **Read Scope:** `docs/agents/orchestrator.md`, `docs/AI_WORKFLOW.md`
- **Depends On:** Group 1
- **Auto-Delegable:** no
- **Escalation Target:** Lead Architect
- **Action:** Add required delegation metadata fields to each step: Role, Write Scope, Read Scope, Depends On, Auto-Delegable, Escalation Target, and Verification.
- **Verification:** `.venv/bin/python scripts/harness/check_docs.py`

#### [x] Step 4: Update client wrapper mappings
- **Role:** Step Implementer
- **Files:** `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- **Write Scope:** `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- **Read Scope:** `docs/agents/orchestrator.md`, `docs/AI_WORKFLOW.md`
- **Depends On:** Step 1
- **Auto-Delegable:** yes
- **Escalation Target:** Lead Architect
- **Action:** Keep wrappers thin while mapping Orchestrator/delegation behavior to each client. Codex must state that subagents are used only when client policy permits; clients without subagents adopt roles locally.
- **Verification:** `.venv/bin/python scripts/harness/check_docs.py`

### Group 3 (depends on: Group 2)
<!-- Add executable checks after the desired documentation shape exists. -->

#### [x] Step 5: Add harness tests for delegation metadata
- **Role:** Test Writer
- **Files:** `tests/harness/test_checks.py`, `tests/harness/test_repository_docs.py`
- **Write Scope:** `tests/harness/test_checks.py`, `tests/harness/test_repository_docs.py`
- **Read Scope:** `scripts/harness/checks.py`, `docs/plans/_TEMPLATE.md`
- **Depends On:** Group 2
- **Auto-Delegable:** yes
- **Escalation Target:** Debugger
- **Action:** Add failing and passing test cases for missing step metadata, overlapping write scopes in parallel groups, missing verification, and valid sequential plans.
- **Verification:** `.venv/bin/pytest tests/harness -q`

#### [x] Step 6: Implement delegation metadata checks
- **Role:** Step Implementer
- **Files:** `scripts/harness/checks.py`
- **Write Scope:** `scripts/harness/checks.py`
- **Read Scope:** `tests/harness/test_checks.py`, `docs/plans/_TEMPLATE.md`
- **Depends On:** Step 5
- **Auto-Delegable:** no
- **Escalation Target:** Debugger
- **Action:** Add standard-library parsing for active plan steps and findings for missing metadata, unsafe same-group write overlap, and missing verification.
- **Verification:** `.venv/bin/pytest tests/harness -q`; `.venv/bin/python scripts/harness/check_docs.py`

### Group 4 (depends on: Group 3)
<!-- Verify, review, and prepare closeout without broad runtime changes. -->

#### [x] Step 7: Run full verification and review
- **Role:** Code Reviewer
- **Files:** No edits expected
- **Write Scope:** None
- **Read Scope:** Modified docs, `scripts/harness/checks.py`, `tests/harness/`
- **Depends On:** Group 3
- **Auto-Delegable:** yes
- **Escalation Target:** Debugger
- **Action:** Review implementation against the SPEC and the existing workflow invariants, then run focused and full verification.
- **Verification:** `.venv/bin/python scripts/harness/check_docs.py`; `.venv/bin/python scripts/harness/verify.py --ci`; `.venv/bin/pytest tests/harness -q`; `.venv/bin/pytest`

#### [x] Step 8: Close documentation lifecycle
- **Role:** Lead Architect
- **Files:** `docs/specs/2026-05-07-repo-native-multi-agent-delegation-protocol.md`, `docs/plans/2026-05-07-repo-native-multi-agent-delegation-protocol.md`, `docs/adrs/2026-05-07-repo-native-multi-agent-delegation-protocol.md`, `docs/wip_state.md`
- **Write Scope:** Listed files and archive destinations
- **Read Scope:** `docs/DOCUMENTATION_WORKFLOW.md`, `docs/AI_WORKFLOW.md`
- **Depends On:** Step 7
- **Auto-Delegable:** no
- **Escalation Target:** Lead Architect
- **Action:** After review passes, update statuses, archive the implemented SPEC and completed PLAN, update ADR references to archived paths, and refresh handoff state.
- **Verification:** `.venv/bin/python scripts/harness/verify.py --ci`; `.venv/bin/pytest`

## Constraints & Architecture
- Keep `docs/AI_WORKFLOW.md` authoritative for pipeline behavior.
- Keep `docs/agents/` authoritative for cross-client role behavior.
- Keep `CLAUDE.md` and `GEMINI.md` as thin wrappers.
- Do not depend on Ruflo, Claude Flow, Skillshare, or any other external orchestration tool for correctness.
- Use only Python standard-library code in harness changes.
- Apply checks to active plans and templates first; archived historical plans should not need metadata backfills unless the implementation deliberately scopes that migration.
- Prefer sequential execution when write ownership or dependency safety is ambiguous.

## Verification
- [x] `.venv/bin/pytest tests/harness/test_checks.py -q`
- [x] `.venv/bin/pytest tests/harness/test_repository_docs.py -q`
- [x] `.venv/bin/pytest tests/harness -q`
- [x] `.venv/bin/python scripts/harness/check_docs.py`
- [x] `.venv/bin/python scripts/harness/verify.py --ci`
- [x] `.venv/bin/pytest`
