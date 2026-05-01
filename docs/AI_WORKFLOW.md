# AI Workflow & Orchestration Protocol

This document defines the execution pipeline for approved work. The active AI assistant (Orchestrator) reads this when the user triggers pipeline work ("implement", "build this", "plan next milestone", or approves a plan).

Documentation lifecycle rules live in `docs/DOCUMENTATION_WORKFLOW.md`.

---

## Session Initialization & Handoff

To ensure continuity between different AI assistants (Claude, Gemini, etc.) and sessions:

1. **Initialization:** At the start of every session, the AI MUST read `docs/wip_state.md` and continue from where the last session left off.
2. **Handoff:** When "preparing handoff", "saving state", or ending a session, the AI MUST overwrite `docs/wip_state.md` with:
   - **Last worker:** [Your name, e.g., Claude Code, Gemini CLI]
   - **Current Objective:** [1-2 lines, reference active plan if applicable]
   - **Last Action:** [Specific]
   - **Modified Files:** [List or "None"]
   - **Current State / Blocker:** [Exact error or remaining logic]
   - **Next Step:** [Exact technical instruction to resume]
   - **Resume Prompt:** [Copy-paste-ready prompt for the next AI worker. Must mention which docs to read first, which SPEC/PLAN to use if implementation is authorized, what verification to run, and which adjacent planned items must not be implemented unless explicitly requested.]

## Canonical Commands

Living command references are centralized in `docs/harness/COMMANDS.md`.

- Advisory harness diagnostics: `.venv/bin/python scripts/harness/check_docs.py`
- Local CI harness verification: `.venv/bin/python scripts/harness/verify.py --ci`
- Full test suite: `.venv/bin/pytest`

---

## Architectural Invariants

Non-negotiable rules. Flag violations immediately during review.

| Invariant | Detail |
|---|---|
| Milliunits | YNAB amounts are ×1000. Expenses are negative. |
| YNAB source of truth | When YNAB provides the relevant financial state, prefer it over locally inferred or cached interpretations. |
| Financial read matrix | Spending totals use transactions, budget health uses category snapshots, account balances use account fields, and recent/edit/undo state is convenience-only. |
| Dependency Injection | Use `YNABRepositoryFactory` per-user. Never singletons. |
| Per-user isolation | All SQLite queries and YNAB calls scoped to authenticated user. |
| UI language | All user-facing strings in Spanish. |
| Database layer | `DatabaseManager` with versioned, reversible migrations. |
| Test coverage | Every new module needs corresponding tests. No regressions allowed. |

---

## Pipeline: Spec → Plan → Implement → Review → Done

Before implementation starts, the assistant must follow `docs/DOCUMENTATION_WORKFLOW.md`:

1. Confirm there is an approved SPEC in `docs/specs/`
2. Produce or refine a PLAN in `docs/plans/` from that SPEC
3. Implement only after the PLAN is implementation-ready
4. Write an ADR in `docs/adrs/` if a significant architectural decision is made or finalized

### 1. Plan

Use the **Lead Architect** role to confirm or create the required documentation:

- For a new feature or refactor: draft or refine the SPEC first using `docs/specs/_TEMPLATE.md`
- For implementation-ready work: draft the PLAN from the approved SPEC using `docs/plans/_TEMPLATE.md`

- For a milestone: "Plan the next milestone from ROADMAP.md."
- For a specific feature: "Plan the feature '<feature name>' from ROADMAP.md."

The architect must ensure the PLAN references its source SPEC. If DB changes are involved, the plan must flag that the **Database Advisor** role must be consulted before implementation.

### 2. Implement

Execute the plan **group by group** in order:

1. For each group, identify all steps and their logical role targets:
   - **DB steps** (migrations, schema, complex queries): use **Database Advisor** first for review, then **Step Implementer**.
   - **All other steps**: use **Step Implementer**.
2. **Execute steps within a group in parallel** whenever the AI platform supports it and files do not conflict.
3. Include in every delegation/step: the exact step, file paths, constraints, and relevant invariants from the table above.
4. **Wait for the entire group to complete** before starting the next group. Review all outputs against the plan.
5. **If any step fails:**
   - Use the **Debugger** role with the full error output, the step context, and the relevant file paths.
   - Once fixed, re-run the step's tests to verify, then continue the pipeline.
   - If an architectural issue is found, **halt the pipeline** and surface it to the user.

### 3. Review

When all groups are complete:

1. **Use the Code Reviewer role:**
   - Review the implementation of `docs/plans/<feature>.md`.
   - Confirm the implementation still matches the source SPEC.
   - **Modified files**: [list]
   - **Feature context**: [summary]
   - **Key invariants to check**: milliunits, DI via factory, Spanish UI, per-user isolation.

2. **Evaluate the report.** The Orchestrator makes the final call:
   - **PASS**: Proceed to close out.
   - **PASS WITH WARNINGS**: Decide which warnings to fix (via Step Implementer).
   - **NEEDS CHANGES**: Fix and re-review.

3. **Check coverage.** If review flags missing tests:
   - Use the **Test Writer** role for specific files/methods.
   - Re-run full suite.

4. **Architectural review** (for complex features): use the **Lead Architect** role.

### 4. Done

Once review passes:
1. Move the plan to `docs/plans/archive/`.
2. Move the implemented SPEC to `docs/specs/archive/`.
3. Preserve references to the archived PLAN and SPEC in any related ADRs.
4. Update `ROADMAP.md` to mark the feature as complete.
5. Write or update the ADR if the feature introduced a significant architectural decision.
6. If all features in a milestone are done, mark the milestone as complete.
7. Update `docs/wip_state.md` to reflect current state.

---

## Model Equality & Autonomy

1. **Active Leadership:** The AI assistant currently in session is the **Lead Orchestrator**. It has full authority and responsibility to execute the entire pipeline (Spec → Plan → Implement → Review → Done).
2. **Role Adoption:** If an AI lacks a multi-agent sub-system, it MUST adopt the logical roles itself (e.g., "I am now acting as **Step Implementer**").
3. **No Hierarchy:** No AI model is "secondary". Every model must strive for the same high standards of architecture, testing, and documentation.

---

## Role Definitions (AI-Specific Mapping)

Each AI assistant maps these logical roles to their own specific capabilities (sub-agents, skills, or specialized prompts). See `CLAUDE.md`, `GEMINI.md`, or `AGENTS.md` for the specific mapping.

| Logical Role | Responsibility |
|---|---|
| **Lead Architect** | Milestone planning, architectural reviews, high-level design. |
| **Database Advisor** | Schema design, migration review, complex SQL optimization. |
| **Step Implementer** | Coding individual plan steps, following architectural patterns. |
| **Code Reviewer** | Reviewing implementation against invariants and best practices. |
| **Test Writer** | Writing unit and integration tests, increasing coverage. |
| **Debugger** | Root-cause analysis and fixing of test failures or reported bugs. |
| **Refactor Advisor** | Identifying cleanup opportunities and reducing technical debt. |

---

## Universal Rules

1. **One step at a time.** Never implement multiple unrelated steps in a single tool call.
2. **Review via Code Reviewer after final implementation.**
3. **Never edit `src/` or `tests/` directly.** Always act through the appropriate implementation role/sub-agent to ensure quality and test coverage.
4. **Treat YNAB as authoritative.** If users can also change data directly in YNAB, the app must reconcile to YNAB rather than assume the bot's local interpretation is complete.
