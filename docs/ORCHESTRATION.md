# Orchestration Protocol

This document defines the full pipeline for feature implementation. The main Claude Code session reads this when the user triggers pipeline work ("implement", "build this", "plan next milestone", or approves a plan).

---

## Architectural Invariants

Non-negotiable rules. Flag violations immediately during review.

| Invariant | Detail |
|---|---|
| Milliunits | YNAB amounts are ×1000. Expenses are negative. |
| Dependency Injection | Use `YNABRepositoryFactory` per-user. Never singletons. |
| Per-user isolation | All SQLite queries and YNAB calls scoped to authenticated user. |
| UI language | All user-facing strings in Spanish. |
| Database layer | `DatabaseManager` with versioned, reversible migrations. |
| Test coverage | ~86%+. Every new module needs corresponding tests. |

---

## Pipeline: Plan → Implement → Review → Done

### 1. Plan

Delegate to `ynab-lead-architect`:

```
Plan the next milestone from ROADMAP.md.
```

Or for a specific feature:

```
Plan the feature "<feature name>" from ROADMAP.md.
```

The architect produces a plan in `docs/plans/<feature>.md` using `docs/plans/_TEMPLATE.md`. If DB changes are involved, the plan will flag that `dba-advisor` must be consulted before implementation.

### 2. Implement

Execute the plan **group by group** in order:

1. For each group, identify all steps and their agent targets:
   - **DB steps** (migrations, schema, complex queries): delegate to `dba-advisor` first for review, then delegate to `plan-step-implementer`.
   - **All other steps**: delegate directly to `plan-step-implementer`.
2. **Launch all steps within a group in parallel** (multiple Agent calls in the same turn).
3. Include in every delegation: the exact step, file paths, constraints, and relevant invariants from the table above.
4. **Wait for the entire group to complete** before starting the next group. Review all outputs against the plan.
5. **If any step fails:**
   - Delegate to `debugger` with the full error output, the step context, and the relevant file paths.
   - Once `debugger` reports the fix, re-run the step's tests to verify, then continue the pipeline.
   - If `debugger` reports an architectural issue, **halt the pipeline** and surface it to the user.

### 3. Review

When all groups are complete:

1. **Delegate code review to `code-reviewer`:**

```
Review the implementation of `docs/plans/<feature>.md`:

**Modified files**: <list all files created/modified across all groups>
**Feature context**: <1-2 sentence summary of what was built>
**Key invariants to check**: milliunits (×1000, negated for expenses), DI via YNABRepositoryFactory (per-user), all UI strings in Spanish, per-user data isolation.
```

2. **Evaluate the report.** You (the orchestrator) make the final call:
   - **PASS**: Proceed to close out.
   - **PASS WITH WARNINGS**: Decide which warnings to accept vs fix. For fixes, delegate to `plan-step-implementer` with specific instructions.
   - **NEEDS CHANGES**: Delegate fixes, then re-request review.

3. **Check coverage.** If `code-reviewer` flags missing tests or coverage dropped:
   - Delegate to `test-writer` with the specific files/methods that need tests.
   - Re-run the full suite to confirm.

4. **Architectural review** (for complex features): delegate to `ynab-lead-architect`:

```
Review the architecture of the implementation in `docs/plans/<feature>.md`:

**Modified files**: <list>
**Feature context**: <summary>
**Concerns**: <specific architectural questions>
```

For straightforward implementations, verify invariants yourself.

### 4. Done

Once review passes:
1. Move the plan from `docs/plans/<feature>.md` to `docs/plans/archive/`.
2. Update `ROADMAP.md` to mark the feature as complete.
3. If all features in a milestone are done, mark the milestone as complete.
4. Update `docs/wip_state.md` to reflect current state.

---

## Delegation Templates

### To `plan-step-implementer`

```
Implement step N from the plan `docs/plans/<feature>.md`:

**Step**: <paste the exact step verbatim from the plan>
**Files**: <list of files to create/modify>
**Constraints**:
- <relevant invariants from the table above>
- <relevant architectural patterns from docs/ARCHITECTURE.md>
**Acceptance criteria**: <what "done" looks like for this step>
```

### To `dba-advisor`

```
Review the following database change for `docs/plans/<feature>.md`:

**Context**: <what the feature does and why the DB change is needed>
**Proposed change**: <schema, migration, or query to review>
**Specific concerns**: <performance? normalization? migration safety?>
```

### To `code-reviewer`

```
Review the implementation of `docs/plans/<feature>.md`:

**Modified files**: <list>
**Feature context**: <summary>
**Key invariants to check**: milliunits, DI via factory, Spanish UI, per-user isolation
```

### To `test-writer`

```
Write tests for the following implementation:

**Source files**: <list of files that need test coverage>
**Existing test files**: <list, or "none">
**What to test**: <specific behaviors, edge cases, or scenarios>
**Fixtures available**: Check tests/conftest.py for mock_ynab_factory, mock_user_repository, etc.
```

### To `debugger`

```
A test failure occurred during implementation of `docs/plans/<feature>.md`:

**Error output**: <paste full error/stack trace>
**Step context**: <what was being implemented>
**Files involved**: <list>
```

### To `refactor-advisor`

```
Analyze the following area for refactoring opportunities:

**Scope**: <file(s) or module to analyze>
**Trigger**: <why — e.g., "module exceeds 300 lines", "duplicated logic", user request>
**Constraints**: <what must NOT change — e.g., external interfaces, test behavior>
```

---

## Delegation Rules

1. **One step per Agent call.** Never batch unrelated steps into a single invocation.
2. **Parallelize within groups.** Launch all steps in the same group as simultaneous Agent calls in one turn.
3. **Synchronize between groups.** Wait for all Agent calls in a group to return, review their outputs, then proceed to the next group.
4. **Route failures to `debugger`.** Don't halt immediately — let `debugger` attempt a fix first. Only halt if the issue is architectural.
5. **Carry context forward.** When starting a new group, summarize relevant outputs from prior groups in each delegation prompt.
6. **No file conflicts in parallel.** Before launching a group, verify that no two parallel steps modify the same file. If they do, split them into sequential groups.
7. **Review via `code-reviewer` after final group.**
8. **Coverage check via `test-writer` if needed.** After review, if coverage dropped or new code lacks tests.
9. **Never edit `src/` or `tests/` yourself.** Always delegate to the appropriate subagent.