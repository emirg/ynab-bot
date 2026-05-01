from pathlib import Path
import json

from scripts.harness.checks import (
    FAIL,
    PASS,
    WARN,
    Finding,
    exit_code_for_findings,
    format_findings,
    format_findings_json,
    run_checks,
)


VALID_RAILWAY_TOML = (
    "[build]\n"
    'buildCommand = "pip install -r requirements.txt && '
    'python scripts/harness/verify.py --ci && pytest"\n'
    "\n"
    "[deploy]\n"
    'startCommand = "python main.py"\n'
    'healthcheckPath = "/"\n'
)

VALID_BEHAVIORAL_MANIFEST = """
[[fixture]]
id = "split_spending_expands_negative_subtransactions"
label = "Split spending expands negative subtransactions"
risk_area = "transaction aggregation"
protected_rule = "Split parent transactions must use negative subtransactions for spending totals."
owner_path = "src/domain/services/spending_aggregation.py"
assertion = "split_spending_expands_negative_subtransactions"

[[fixture.pytest_evidence]]
path = "tests/domain/services/test_spending_aggregation.py"
snippet = "def test_summarize_transaction_spending_uses_expanded_split_entries"

[[fixture.doc_evidence]]
path = "docs/AI_WORKFLOW.md"
snippet = "Milliunits"

[[fixture]]
id = "zero_sum_shared_split_counts_negative_leg"
label = "Zero-sum shared split negative leg counts as spending"
risk_area = "shared expense aggregation"
protected_rule = "Zero-sum shared transactions still count the user's negative spending leg."
owner_path = "src/domain/services/spending_aggregation.py"
assertion = "zero_sum_shared_split_counts_negative_leg"

[[fixture.pytest_evidence]]
path = "tests/domain/services/test_spending_aggregation.py"
snippet = "def test_summarize_transaction_spending_counts_zero_sum_shared_split_expenses"

[[fixture.doc_evidence]]
path = "docs/AI_WORKFLOW.md"
snippet = "YNAB source of truth"

[[fixture]]
id = "net_spending_offsets_categorized_inflows"
label = "Net spending offsets categorized inflows and hides positive-net categories"
risk_area = "monthly net spending"
protected_rule = "Categorized inflows reduce period spending while Ready to Assign inflows are excluded."
owner_path = "src/domain/services/spending_aggregation.py"
assertion = "net_spending_offsets_categorized_inflows"

[[fixture.pytest_evidence]]
path = "tests/domain/services/test_spending_aggregation.py"
snippet = "def test_summarize_transaction_net_spending_offsets_category_inflows"

[[fixture.doc_evidence]]
path = "docs/AI_WORKFLOW.md"
snippet = "Financial read matrix"

[[fixture]]
id = "budget_snapshots_preserve_balance"
label = "Budget category snapshots preserve YNAB balances and filter inactive categories"
risk_area = "budget health"
protected_rule = "Budget health must use YNAB category balance snapshots and ignore inactive categories."
owner_path = "src/domain/services/spending_aggregation.py"
assertion = "budget_snapshots_preserve_balance"

[[fixture.pytest_evidence]]
path = "tests/domain/services/test_spending_aggregation.py"
snippet = "def test_normalize_budget_category_snapshots_filters_inactive_hidden_and_deleted"

[[fixture.doc_evidence]]
path = "docs/AI_WORKFLOW.md"
snippet = "Spending totals use transactions"

[[fixture]]
id = "edit_reconciliation_trusts_live_identity"
label = "Edit reconciliation trusts existing live YNAB transaction identity"
risk_area = "recent edit reconciliation"
protected_rule = "/editar must trust an existing live YNAB transaction id despite local recent drift."
owner_path = "src/application/services/expense_service.py"
assertion = "edit_reconciliation_trusts_live_identity"

[[fixture.pytest_evidence]]
path = "tests/application/services/test_expense_service.py"
snippet = "def test_missing_live_ynab_transaction_blocks_edit"

[[fixture.doc_evidence]]
path = "docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md"
snippet = "local recent metadata can drift"

[[fixture]]
id = "undo_reconciliation_blocks_stale_recent_reference"
label = "Undo reconciliation blocks stale local recent references"
risk_area = "recent undo reconciliation"
protected_rule = "/deshacer must block stale local recent references before destructive deletion."
owner_path = "src/application/services/expense_service.py"
assertion = "undo_reconciliation_blocks_stale_recent_reference"

[[fixture.pytest_evidence]]
path = "tests/application/services/test_expense_service.py"
snippet = "def test_success_removes_from_recent_transactions"

[[fixture.doc_evidence]]
path = "docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md"
snippet = "ADR: Recent Edit Live YNAB Reconciliation"

[[fixture]]
id = "shared_expense_construction_preserves_zero_sum"
label = "Shared expense construction preserves zero-sum balance"
risk_area = "shared expense aggregation"
protected_rule = "Other-paid split transactions must be zero-sum with balancing subtransactions."
owner_path = "src/domain/models/expense.py"
assertion = "shared_expense_construction_preserves_zero_sum"

[[fixture.pytest_evidence]]
path = "tests/domain/models/test_domain_models.py"
snippet = "def test_to_ynab_format_other_paid_zero_sum"

[[fixture.doc_evidence]]
path = "docs/AI_WORKFLOW.md"
snippet = "Milliunits"

[[fixture]]
id = "account_balance_reads_from_account_fields"
label = "Account balance queries read from account fields"
risk_area = "account balance source"
protected_rule = "Account balance queries must read directly from account fields (balance, cleared_balance)."
owner_path = "src/application/services/budget_query_service.py"
assertion = "account_balance_reads_from_account_fields"

[[fixture.pytest_evidence]]
path = "tests/application/services/test_budget_query_service.py"
snippet = "def test_exact_match"

[[fixture.doc_evidence]]
path = "docs/AI_WORKFLOW.md"
snippet = "account balances use account fields"
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_minimal_repo(root: Path) -> None:
    write(root / "docs/AI_WORKFLOW.md", "# AI Workflow\n")
    write(root / "docs/DOCUMENTATION_WORKFLOW.md", "# Documentation Workflow\n")
    write(
        root / "docs/wip_state.md",
        "Last worker: Codex\n"
        "Current Objective: Minimal fixture repo.\n"
        "Last Action: Created fixture state.\n"
        "Modified Files: None\n"
        "Current State / Blocker: No blocker.\n"
        "Next Step: Run harness tests.\n"
        "Resume Prompt: Read AGENTS.md, docs/AI_WORKFLOW.md, "
        "docs/DOCUMENTATION_WORKFLOW.md, and docs/wip_state.md first.\n",
    )
    write(root / "docs/specs/_TEMPLATE.md", "# Spec Template\n")
    write(root / "docs/plans/_TEMPLATE.md", "# Plan Template\n")
    write(root / "docs/adrs/_TEMPLATE.md", "# ADR Template\n")
    write(
        root / "docs/harness/COMMANDS.md",
        "# Harness Commands\n\n"
        "- `.venv/bin/python main.py`\n"
        "- `.venv/bin/pytest`\n"
        "- `.venv/bin/python scripts/harness/check_docs.py`\n"
        "- `.venv/bin/python scripts/harness/check_financial_invariants.py`\n"
        "- `.venv/bin/python scripts/harness/check_behavioral_invariants.py`\n"
        "- `.venv/bin/python scripts/harness/verify.py --ci`\n"
        "- `python scripts/harness/verify.py --ci`\n"
        "- `pip install -r requirements.txt && python scripts/harness/verify.py --ci && pytest`\n",
    )
    write(root / "ROADMAP.md", "# Roadmap\n")
    write(root / "railway.toml", VALID_RAILWAY_TOML)
    write(root / "scripts/harness/behavioral_invariants.toml", VALID_BEHAVIORAL_MANIFEST)
    (root / "docs/specs/archive").mkdir(parents=True)
    (root / "docs/plans/archive").mkdir(parents=True)
    write(
        root / "AGENTS.md",
        "# AGENTS.md\n\n"
        "Read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.\n"
        "Commands are documented in `docs/harness/COMMANDS.md`.\n"
        "YNAB is the financial source of truth for this project.\n"
        "When the user triggers a handoff, overwrite `docs/wip_state.md`.\n",
    )
    write(
        root / "CLAUDE.md",
        "# CLAUDE.md\n\n"
        "Read and follow `AGENTS.md` first. This file only maps project workflow roles to Claude Code capabilities.\n\n"
        "## Role Mapping\n\n"
        "| Logical Role | Claude Agent |\n"
        "|---|---|\n"
        "| **Lead Architect** | `ynab-lead-architect` |\n"
        "| **Database Advisor** | `dba-advisor` |\n"
        "| **Step Implementer** | `plan-step-implementer` |\n"
        "| **Code Reviewer** | `code-reviewer` |\n"
        "| **Test Writer** | `test-writer` |\n"
        "| **Debugger** | `debugger` |\n"
        "| **Refactor Advisor** | `refactor-advisor` |\n",
    )
    write(
        root / "GEMINI.md",
        "# GEMINI.md\n\n"
        "Read and follow `AGENTS.md` first. This file only maps project workflow roles to Gemini CLI capabilities.\n\n"
        "## Role Mapping\n\n"
        "| Logical Role | Gemini Capability |\n"
        "|---|---|\n"
        "| **Lead Architect** | Activate `writing-plans` skill |\n"
        "| **Database Advisor** | Use `codebase_investigator` for schema review |\n"
        "| **Step Implementer** | Direct tool use |\n"
        "| **Code Reviewer** | Self-review against invariants |\n"
        "| **Test Writer** | Activate `Pytest Testing` skill |\n"
        "| **Debugger** | Use `codebase_investigator` for root cause |\n"
        "| **Refactor Advisor** | Use `python-design-patterns` skill |\n",
    )
    write(
        root / "docs/AI_WORKFLOW.md",
        "# AI Workflow\n\n"
        "| Milliunits | YNAB amounts are ×1000. Expenses are negative. |\n"
        "| YNAB source of truth | Prefer YNAB over cached interpretations. |\n"
        "| Financial read matrix | Spending totals use transactions, budget health uses category snapshots, "
        "account balances use account fields, and recent/edit/undo state is convenience-only. |\n\n"
        "Run `.venv/bin/python scripts/harness/check_docs.py` locally.\n"
        "Run `.venv/bin/python scripts/harness/verify.py --ci` before closing work.\n",
    )
    write(
        root / "docs/adrs/2026-04-12-ynab-source-of-truth.md",
        "# ADR: YNAB Source of Truth\n\n"
        "YNAB is the financial source of truth for this project.\n"
        "Monthly budget-health and availability decisions should prefer YNAB category activity/balance.\n"
        "Monthly spending totals still come from transactions.\n"
        "- **Related Spec:** `docs/specs/archive/2026-04-12-ynab-source-of-truth-hardening.md`\n"
        "- **Related Plan:** `docs/plans/archive/2026-04-12-ynab-source-of-truth-hardening.md`\n",
    )
    write(
        root / "docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md",
        "# ADR: Recent Edit Live YNAB Reconciliation\n\n"
        "local recent metadata can drift from YNAB and should not override live YNAB.\n"
        "- **Related Spec:** `docs/specs/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`\n"
        "- **Related Plan:** `docs/plans/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`\n",
    )
    write(
        root / "docs/specs/archive/2026-04-12-ynab-source-of-truth-hardening.md",
        "# Spec: YNAB Source Of Truth\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap:** Ignore\n",
    )
    write(
        root / "docs/plans/archive/2026-04-12-ynab-source-of-truth-hardening.md",
        "# Plan: YNAB Source Of Truth\n\n"
        "## Objective & Context\n"
        "- **Status:** Completed\n"
        "- **Source Spec:** `docs/specs/archive/2026-04-12-ynab-source-of-truth-hardening.md`\n"
        "- **Harness Roadmap:** Ignore\n"
        "- [x] Done\n",
    )
    write(
        root / "docs/specs/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md",
        "# Spec: Recent Edit Reconciliation\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap:** Ignore\n",
    )
    write(
        root / "docs/plans/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md",
        "# Plan: Recent Edit Reconciliation\n\n"
        "## Objective & Context\n"
        "- **Status:** Completed\n"
        "- **Source Spec:** `docs/specs/archive/2026-04-25-fix-recent-transaction-edit-reconciliation.md`\n"
        "- **Harness Roadmap:** Ignore\n"
        "- [x] Done\n",
    )
    write(
        root / "src/domain/models/expense.py",
        "class Expense:\n"
        "    def to_ynab_transaction(self):\n"
        "        amount_milliunits = int(self.amount * -1000)\n"
        "        return {\"amount\": amount_milliunits}\n",
    )
    write(
        root / "src/domain/services/spending_aggregation.py",
        "def extract_expense_entries(transactions):\n"
        "    entries = []\n"
        "    for txn in transactions:\n"
        "        negative_subtransactions = [sub for sub in (txn.get('subtransactions') or []) if sub.get('amount', 0) < 0]\n"
        "        if negative_subtransactions:\n"
        "            for sub in negative_subtransactions:\n"
        "                entries.append({'amount': sub['amount'], 'category_name': sub.get('category_name') or 'Sin categoría', 'date': txn.get('date', '')})\n"
        "            continue\n"
        "        if txn.get('transfer_account_id') or txn.get('transfer_transaction_id'):\n"
        "            continue\n"
        "        amount = txn.get('amount', 0)\n"
        "        if amount < 0:\n"
        "            entries.append({'amount': amount, 'category_name': txn.get('category_name') or 'Sin categoría', 'date': txn.get('date', '')})\n"
        "    return entries\n\n"
        "def summarize_transaction_spending(transactions):\n"
        "    entries = extract_expense_entries(transactions)\n"
        "    total = sum(abs(entry['amount']) for entry in entries)\n"
        "    categories = {}\n"
        "    for entry in entries:\n"
        "        categories[entry['category_name']] = categories.get(entry['category_name'], 0) + abs(entry['amount'])\n"
        "    return total, categories\n\n"
        "def summarize_transaction_net_spending(transactions):\n"
        "    net_activity_by_key = {}\n"
        "    names = {}\n"
        "    rows = []\n"
        "    for txn in transactions:\n"
        "        if txn.get('transfer_account_id') or txn.get('transfer_transaction_id'):\n"
        "            continue\n"
        "        rows.extend(txn.get('subtransactions') or [txn])\n"
        "    for row in rows:\n"
        "        amount = row.get('amount', 0)\n"
        "        if amount == 0:\n"
        "            continue\n"
        "        name = row.get('category_name') or 'Sin categoría'\n"
        "        if amount > 0 and (not row.get('category_id') or name.startswith('Inflow:')):\n"
        "            continue\n"
        "        key = 'id:' + row.get('category_id') if row.get('category_id') else 'name:' + name\n"
        "        net_activity_by_key[key] = net_activity_by_key.get(key, 0) + amount\n"
        "        names[key] = name\n"
        "    total = max(0, -sum(net_activity_by_key.values()))\n"
        "    categories = {names[key]: abs(amount) for key, amount in net_activity_by_key.items() if amount < 0}\n"
        "    return total, categories\n\n"
        "def normalize_budget_category_snapshots(categories):\n"
        "    snapshots = []\n"
        "    for category in categories:\n"
        "        hidden = category.get('hidden', False)\n"
        "        deleted = category.get('deleted', False)\n"
        "        budgeted = category.get('budgeted', 0)\n"
        "        activity = category.get('activity', 0)\n"
        "        balance = category.get('balance', 0)\n"
        "        if deleted or hidden or (budgeted <= 0 and activity == 0):\n"
        "            continue\n"
        "        snapshots.append({\"name\": category.get('name', ''), \"budgeted\": budgeted, \"activity\": activity, \"balance\": balance})\n"
        "    return snapshots\n",
    )
    write(
        root / "src/application/services/budget_query_service.py",
        "class BudgetQueryService:\n"
        "    def _query_budget_summary(self, transactions):\n"
        "        total_spent, category_totals = summarize_transaction_net_spending(transactions)\n"
        "        return total_spent, category_totals\n\n"
        "    def _query_account_balance(self, accounts, target_name):\n"
        "        return {\n"
        "            'balance': account.balance,\n"
        "            'cleared_balance': account.cleared_balance,\n"
        "            'uncleared_balance': account.uncleared_balance,\n"
        "        }\n",
    )
    write(
        root / "src/application/services/advisor_dashboard_service.py",
        "from domain.services.spending_aggregation import normalize_budget_category_snapshots\n\n"
        "def _build_budget_status(entry):\n"
        "    remaining = entry[\"balance\"]\n"
        "    return remaining\n",
    )
    write(
        root / "src/application/services/expense_service.py",
        "class ExpenseService:\n"
        "    @staticmethod\n"
        "    def _normalize_recent_amount_for_reconciliation(amount):\n"
        "        return int(abs(amount) * -1000) if amount is not None else None\n\n"
        "    @staticmethod\n"
        "    def _normalize_payee_name(payee):\n"
        "        return str(payee or '').casefold().strip()\n\n"
        "    def _cached_category_matches_live(self, cached_category_id, live_transaction):\n"
        "        return not cached_category_id or cached_category_id == live_transaction.get('category_id')\n\n"
        "    def _get_live_transaction_state_for_edit(self, ynab_repository, budget_id, cached_transaction):\n"
        "        transaction_id = cached_transaction.get('ynab_transaction_id')\n"
        "        if not transaction_id:\n"
        "            return None, 'no_ynab_transaction_id'\n"
        "        live = ynab_repository.get_transaction_by_id(budget_id, transaction_id)\n"
        "        if live is None:\n"
        "            return None, 'ynab_transaction_missing'\n"
        "        return live, None\n\n"
        "    def _get_live_transaction_state(self, ynab_repository, budget_id, cached_transaction):\n"
        "        transaction_id = cached_transaction.get('ynab_transaction_id')\n"
        "        if not transaction_id:\n"
        "            return None, 'no_ynab_transaction_id'\n"
        "        live = ynab_repository.get_transaction_by_id(budget_id, transaction_id)\n"
        "        if live is None:\n"
        "            return None, 'ynab_transaction_missing'\n"
        "        expected = self._normalize_recent_amount_for_reconciliation(cached_transaction.get('amount'))\n"
        "        if expected is not None and live.get('amount') != expected:\n"
        "            return None, 'ynab_transaction_stale'\n"
        "        if self._normalize_payee_name(cached_transaction.get('payee')) != self._normalize_payee_name(live.get('payee_name')):\n"
        "            return None, 'ynab_transaction_stale'\n"
        "        if not self._cached_category_matches_live(cached_transaction.get('category_id'), live):\n"
        "            return None, 'ynab_transaction_stale'\n"
        "        return live, None\n\n"
        "    def edit_last_transaction(self):\n"
        "        self.learning_repository.update_recent_transaction(telegram_user_id, ynab_transaction_id, {})\n\n"
        "    def undo_last_transaction(self):\n"
        "        self.learning_repository.delete_recent_transaction(telegram_user_id, ynab_transaction_id)\n",
    )
    write(
        root / "tests/domain/models/test_domain_models.py",
        "def test_to_ynab_format_with_valid_category():\n"
        "    assert txn['amount'] == -25000000\n",
    )
    write(
        root / "tests/domain/services/test_spending_aggregation.py",
        "def test_summarize_transaction_spending_uses_expanded_split_entries():\n"
        "    assert True\n\n"
        "def test_summarize_transaction_spending_counts_zero_sum_shared_split_expenses():\n"
        "    assert True\n\n"
        "def test_summarize_transaction_net_spending_offsets_category_inflows():\n"
        "    assert True\n\n"
        "def test_summarize_transaction_net_spending_nets_split_tracking_inflows_against_month_total():\n"
        "    assert True\n\n"
        "def test_normalize_budget_category_snapshots_filters_inactive_hidden_and_deleted():\n"
        "    assert True\n",
    )
    write(
        root / "tests/application/services/test_budget_query_service.py",
        "class TestAccountBalance:\n"
        "    def test_exact_match(self):\n"
        "        assert \"cleared_balance\" == \"cleared_balance\"\n\n"
        "        assert result.data['balance'] == -500000\n"
        "        assert result.data['cleared_balance'] == -400000\n\n"
        "class TestBudgetSummary:\n"
        "    def test_budget_summary_uses_transactions_for_spending_totals_and_top_categories(self):\n"
        "        assert True\n\n"
        "    def test_budget_summary_nets_category_inflows_from_transactions(self):\n"
        "        assert True\n",
    )
    write(
        root / "tests/application/services/test_advisor_dashboard_service.py",
        "def test_build_dashboard_month_uses_balance_for_overspending():\n"
        "    assert True\n",
    )
    write(
        root / "tests/application/services/test_expense_service.py",
        "def test_missing_live_ynab_transaction_blocks_edit():\n"
        "    assert True\n\n"
        "def test_successful_edit_refreshes_recent_cache_from_live_transaction():\n"
        "    assert True\n\n"
        "def test_success_removes_from_recent_transactions():\n"
        "    assert True\n\n"
        "def test_stale_live_ynab_transaction_blocks_undo():\n"
        "    assert True\n",
    )
    write(
        root / "docs/specs/2026-04-30-feature.md",
        "# Spec: Feature\n\n"
        "## Metadata\n"
        "- **Status:** Approved\n"
        "- **Owner:** Codex\n",
    )
    write(
        root / "docs/plans/2026-04-30-feature.md",
        "# Plan: Feature\n\n"
        "## Objective & Context\n"
        "- **Status:** In Progress\n"
        "- **Source Spec:** `docs/specs/2026-04-30-feature.md`\n",
    )


def failures(root: Path) -> list[Finding]:
    return [finding for finding in run_checks(root) if finding.severity == FAIL]


def messages_for(root: Path, severity: str) -> set[str]:
    return {finding.message for finding in run_checks(root) if finding.severity == severity}


def test_required_workflow_files_are_enforced(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "docs/AI_WORKFLOW.md").unlink()

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Required workflow file is missing: docs/AI_WORKFLOW.md" in messages


def test_wip_state_requires_resume_prompt(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/wip_state.md",
        "Last worker: Codex\n"
        "Current Objective: Missing resume prompt.\n"
        "Last Action: Removed field.\n"
        "Modified Files: docs/wip_state.md\n"
        "Current State / Blocker: No blocker.\n"
        "Next Step: Restore field.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Handoff state is missing required field: Resume Prompt" in messages


def test_missing_wip_state_warns_without_blocking_ci(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "docs/wip_state.md").unlink()

    warning_messages = messages_for(tmp_path, WARN)
    failure_messages = {finding.message for finding in failures(tmp_path)}

    assert "Handoff state file is absent: docs/wip_state.md" in warning_messages
    assert "Required workflow file is missing: docs/wip_state.md" not in failure_messages


def test_active_spec_and_plan_metadata_are_validated(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/specs/2026-04-29-done.md",
        "# Spec: Done\n\n## Metadata\n- **Status:** Implemented\n",
    )
    write(
        tmp_path / "docs/plans/2026-04-29-broken.md",
        "# Plan: Broken\n\n## Objective & Context\n- **Status:** Completed\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Implemented SPECs must be archived: docs/specs/2026-04-29-done.md" in messages
    assert "Completed PLANs must be archived: docs/plans/2026-04-29-broken.md" in messages
    assert "Active PLAN is missing Source Spec: docs/plans/2026-04-29-broken.md" in messages


def test_archived_docs_must_have_terminal_status(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/specs/archive/2026-04-29-draft-spec.md",
        "# Spec: Draft Archived\n\n"
        "## Metadata\n"
        "- **Status:** Approved\n"
        "- **Harness Roadmap Marker:** E.99\n",
    )
    write(
        tmp_path / "docs/plans/archive/2026-04-29-draft-plan.md",
        "# Plan: Draft Archived\n\n"
        "## Objective & Context\n"
        "- **Status:** Draft\n"
        "- **Source Spec:** `docs/specs/archive/2026-04-29-draft-spec.md`\n"
        "- **Harness Roadmap Marker:** E.99\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Archived SPEC must have Status Implemented: "
        "docs/specs/archive/2026-04-29-draft-spec.md"
    ) in messages
    assert (
        "Archived PLAN must have Status Completed: "
        "docs/plans/archive/2026-04-29-draft-plan.md"
    ) in messages


def test_active_plan_source_spec_must_exist(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/plans/2026-04-29-missing-source.md",
        "# Plan: Missing Source\n\n"
        "## Objective & Context\n"
        "- **Status:** In Progress\n"
        "- **Source Spec:** `docs/specs/2026-04-29-missing-source.md`\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "PLAN Source Spec does not exist: docs/plans/2026-04-29-missing-source.md -> "
        "docs/specs/2026-04-29-missing-source.md"
    ) in messages


def test_adr_spec_and_plan_references_must_exist(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/adrs/2026-04-30-decision.md",
        "# ADR: Decision\n\n"
        "## Metadata\n"
        "- **Status:** Accepted\n"
        "- **Related Spec:** `docs/specs/archive/2026-04-30-feature.md`\n"
        "- **Related Plan:** `docs/plans/archive/2026-04-30-feature.md`\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "ADR reference does not exist: docs/adrs/2026-04-30-decision.md -> "
        "docs/specs/archive/2026-04-30-feature.md"
    ) in messages
    assert (
        "ADR reference does not exist: docs/adrs/2026-04-30-decision.md -> "
        "docs/plans/archive/2026-04-30-feature.md"
    ) in messages


def test_agent_entrypoints_must_reference_workflow_docs(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "AGENTS.md",
        "Read `docs/AI_WORKFLOW.md`.\n"
        "Commands are documented in `docs/harness/COMMANDS.md`.\n"
        "YNAB is the financial source of truth for this project.\n"
        "When the user triggers a handoff, overwrite `docs/wip_state.md`.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "AGENTS.md is missing docs/DOCUMENTATION_WORKFLOW.md reference"
        in messages
    )


def test_stale_orchestration_references_fail(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(tmp_path / ".claude/agents/ynab-lead-architect.md", "Read docs/ORCHESTRATION.md\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Stale docs/ORCHESTRATION.md reference found: .claude/agents/ynab-lead-architect.md"
        in messages
    )


def test_advisory_mode_exits_zero_but_strict_mode_blocks() -> None:
    findings = [Finding(FAIL, "Broken", "docs/example.md")]

    assert exit_code_for_findings(findings, strict=False) == 0
    assert exit_code_for_findings(findings, strict=True) == 1


def test_format_findings_groups_by_severity_and_family() -> None:
    findings = [
        Finding(PASS, "p1", "path1", "fam1"),
        Finding(PASS, "p2", "path2", "fam2"),
        Finding(WARN, "w1", None, "fam1"),
        Finding(FAIL, "f1", "path3", "fam2", "fix it"),
    ]
    output = format_findings(findings)

    assert "FAIL (1)" in output
    assert "  [fam2]" in output
    assert "    - f1 (path3)" in output
    assert "      HINT: fix it" in output

    assert "WARN (1)" in output
    assert "  [fam1]" in output
    assert "    - w1" in output

    assert "PASS (2)" in output
    assert "  [fam1]" in output
    assert "    - p1 (path1)" in output
    assert "  [fam2]" in output
    assert "    - p2 (path2)" in output


def test_format_findings_json_structure() -> None:
    findings = [
        Finding(PASS, "p1", "path1", "fam1", "hint1"),
    ]
    output = json.loads(format_findings_json(findings))

    assert output["summary"]["PASS"] == 1
    assert output["findings"][0]["message"] == "p1"
    assert output["findings"][0]["path"] == "path1"
    assert output["findings"][0]["family"] == "fam1"
    assert output["findings"][0]["hint"] == "hint1"


def test_valid_railway_config_reports_pass_findings(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)

    messages = messages_for(tmp_path, PASS)

    assert "Railway config file exists: railway.toml" in messages
    assert "Railway build command runs harness before pytest: railway.toml" in messages
    assert "Railway start command is expected app entrypoint: railway.toml" in messages


def test_railway_config_file_is_required(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "railway.toml").unlink()

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Required Railway config file is missing: railway.toml" in messages


def test_malformed_railway_config_fails(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(tmp_path / "railway.toml", "[build\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert any(message.startswith("Railway config is not valid TOML: railway.toml") for message in messages)


def test_railway_build_command_must_run_harness(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "railway.toml",
        "[build]\n"
        'buildCommand = "pip install -r requirements.txt && pytest"\n'
        "\n"
        "[deploy]\n"
        'startCommand = "python main.py"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Railway build command is missing harness verification: railway.toml" in messages


def test_railway_build_command_must_run_harness_before_pytest(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "railway.toml",
        "[build]\n"
        'buildCommand = "pip install -r requirements.txt && pytest && '
        'python scripts/harness/verify.py --ci"\n'
        "\n"
        "[deploy]\n"
        'startCommand = "python main.py"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Railway build command runs pytest before harness verification: railway.toml" in messages


def test_railway_start_command_must_use_expected_entrypoint(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "railway.toml",
        "[build]\n"
        'buildCommand = "pip install -r requirements.txt && '
        'python scripts/harness/verify.py --ci && pytest"\n'
        "\n"
        "[deploy]\n"
        'startCommand = "python other.py"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Railway start command must be `python main.py`: railway.toml" in messages


def test_command_registry_document_reports_pass_findings(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)

    messages = messages_for(tmp_path, PASS)

    assert "Command registry document exists: docs/harness/COMMANDS.md" in messages
    assert (
        "Command registry documents local advisory docs command: "
        "docs/harness/COMMANDS.md"
    ) in messages
    assert (
        "Living workflow doc references local CI harness command: docs/AI_WORKFLOW.md"
        in messages
    )
    assert "AGENTS.md references canonical command registry: AGENTS.md" in messages
    assert "Agent wrapper references AGENTS.md: CLAUDE.md" in messages
    assert "Agent wrapper references AGENTS.md: GEMINI.md" in messages


def test_command_registry_document_is_required(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "docs/harness/COMMANDS.md").unlink()

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Command registry document is missing: docs/harness/COMMANDS.md" in messages


def test_command_registry_document_must_include_canonical_commands(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/harness/COMMANDS.md",
        "# Harness Commands\n\n"
        "- `.venv/bin/python main.py`\n"
        "- `.venv/bin/pytest`\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Command registry is missing local advisory docs command: "
        "docs/harness/COMMANDS.md -> .venv/bin/python scripts/harness/check_docs.py"
    ) in messages


def test_agents_must_reference_command_registry(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "AGENTS.md",
        "Read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.\n"
        "YNAB is the financial source of truth for this project.\n"
        "When the user triggers a handoff, overwrite `docs/wip_state.md`.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "AGENTS.md is missing canonical command registry reference" in messages


def test_agent_wrappers_must_reference_agents_md(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "CLAUDE.md",
        "# CLAUDE.md\n\n"
        "This file only maps project workflow roles to Claude Code capabilities.\n\n"
        "## Role Mapping\n\n"
        "| **Lead Architect** | `ynab-lead-architect` |\n"
        "| **Database Advisor** | `dba-advisor` |\n"
        "| **Step Implementer** | `plan-step-implementer` |\n"
        "| **Code Reviewer** | `code-reviewer` |\n"
        "| **Test Writer** | `test-writer` |\n"
        "| **Debugger** | `debugger` |\n"
        "| **Refactor Advisor** | `refactor-advisor` |\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Agent wrapper is missing AGENTS.md reference: CLAUDE.md" in messages


def test_agent_wrappers_must_keep_role_mapping(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "GEMINI.md",
        "# GEMINI.md\n\n"
        "Read and follow `AGENTS.md` first. This file only maps project workflow roles to Gemini CLI capabilities.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Agent wrapper is missing role mapping section: GEMINI.md" in messages
    assert "Agent wrapper role mapping is missing Lead Architect: GEMINI.md" in messages


def test_agent_wrappers_cannot_duplicate_shared_sections(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "GEMINI.md",
        "# GEMINI.md\n\n"
        "Read and follow `AGENTS.md` first. This file only maps project workflow roles to Gemini CLI capabilities.\n\n"
        "## Role Mapping\n\n"
        "| **Lead Architect** | Activate `writing-plans` skill |\n"
        "| **Database Advisor** | Use `codebase_investigator` |\n"
        "| **Step Implementer** | Direct tool use |\n"
        "| **Code Reviewer** | Self-review |\n"
        "| **Test Writer** | Activate `Pytest Testing` skill |\n"
        "| **Debugger** | Use `codebase_investigator` |\n"
        "| **Refactor Advisor** | Use `python-design-patterns` skill |\n\n"
        "## Commands\n\n"
        "Run `.venv/bin/python main.py` and `.venv/bin/pytest`.\n\n"
        "## Source Of Truth\n\n"
        "YNAB is the financial source of truth for this project.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Agent wrapper duplicates shared section `## Commands`: GEMINI.md" in messages
    assert "Agent wrapper duplicates shared section `## Source Of Truth`: GEMINI.md" in messages


def test_workflow_docs_must_reference_harness_commands(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/AI_WORKFLOW.md",
        "# AI Workflow\n\nNo executable harness commands here.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Living workflow doc is missing local advisory docs command "
        "`.venv/bin/python scripts/harness/check_docs.py`: docs/AI_WORKFLOW.md"
    ) in messages
    assert (
        "Living workflow doc is missing local CI harness command "
        "`.venv/bin/python scripts/harness/verify.py --ci`: docs/AI_WORKFLOW.md"
    ) in messages


def test_completed_archived_plan_cannot_have_unchecked_tasks(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/plans/archive/2026-04-30-done.md",
        "# Plan: Done\n\n"
        "## Objective & Context\n"
        "- **Status:** Completed\n"
        "- **Source Spec:** `docs/specs/archive/2026-04-30-done.md`\n"
        "- **Harness Roadmap Marker:** E.99\n\n"
        "## Verification\n"
        "- [x] Checked\n"
        "- [ ] Not checked\n",
    )
    write(
        tmp_path / "docs/specs/archive/2026-04-30-done.md",
        "# Spec: Done\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap Marker:** E.99\n",
    )
    write(tmp_path / "ROADMAP.md", "### E.99 — Done [COMPLETADO]\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Completed archived PLAN has unchecked task boxes: "
        "docs/plans/archive/2026-04-30-done.md"
    ) in messages


def test_implemented_archived_spec_requires_roadmap_marker_present_in_roadmap(
    tmp_path: Path,
) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/specs/archive/2026-04-30-missing-roadmap.md",
        "# Spec: Missing Roadmap\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap Marker:** E.404\n",
    )
    write(tmp_path / "ROADMAP.md", "### E.99 — Other [COMPLETADO]\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Implemented archived SPEC roadmap marker is missing from ROADMAP.md: "
        "docs/specs/archive/2026-04-30-missing-roadmap.md -> E.404"
    ) in messages


def test_roadmap_ignore_metadata_skips_historical_documents(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/specs/archive/2026-04-30-historical.md",
        "# Spec: Historical\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap:** Ignore\n",
    )
    write(
        tmp_path / "docs/plans/archive/2026-04-30-historical.md",
        "# Plan: Historical\n\n"
        "## Objective & Context\n"
        "- **Status:** Completed\n"
        "- **Source Spec:** `docs/specs/archive/2026-04-30-historical.md`\n"
        "- **Harness Roadmap:** Ignore\n"
        "- [ ] Historical unchecked task\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert all("2026-04-30-historical.md" not in message for message in messages)


def test_financial_invariant_evidence_reports_pass_findings(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)

    messages = messages_for(tmp_path, PASS)

    assert "Financial invariant evidence exists: milliunit expense conversion" in messages
    assert "Financial invariant evidence exists: transaction spending totals" in messages
    assert "Financial invariant evidence exists: budget health category snapshots" in messages
    assert "Financial invariant evidence exists: account balances from account fields" in messages
    assert "Financial invariant evidence exists: recent edit undo convenience boundary" in messages


def test_financial_invariant_source_evidence_is_required(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "src/domain/models/expense.py",
        "class Expense:\n"
        "    def to_ynab_transaction(self):\n"
        "        return {\"amount\": self.amount}\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Financial invariant source evidence is missing for milliunit expense conversion: "
        "src/domain/models/expense.py -> amount_milliunits = int(self.amount * -1000)"
    ) in messages


def test_financial_invariant_test_evidence_is_required(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "tests/domain/services/test_spending_aggregation.py",
        "def test_other_behavior():\n"
        "    assert True\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Financial invariant test evidence is missing for transaction spending totals: "
        "tests/domain/services/test_spending_aggregation.py -> "
        "test_summarize_transaction_net_spending_offsets_category_inflows"
    ) in messages


def test_behavioral_invariants_report_pass_findings(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)

    messages = messages_for(tmp_path, PASS)

    assert (
        "Behavioral invariant holds: Split spending expands negative subtransactions "
        "[transaction aggregation: Split parent transactions must use negative subtransactions for spending totals.]"
    ) in messages
    assert (
        "Behavioral invariant holds: Edit reconciliation trusts existing live YNAB transaction identity "
        "[recent edit reconciliation: /editar must trust an existing live YNAB transaction id despite local recent drift.]"
    ) in messages
    assert (
        "Behavioral invariant holds: Undo reconciliation blocks stale local recent references "
        "[recent undo reconciliation: /deshacer must block stale local recent references before destructive deletion.]"
    ) in messages


def test_behavioral_invariant_failures_block_harness(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "src/domain/services/spending_aggregation.py",
        "def summarize_transaction_spending(transactions):\n"
        "    return 0, {}\n\n"
        "def summarize_transaction_net_spending(transactions):\n"
        "    net_activity_by_key = {}\n"
        "    return 0, net_activity_by_key\n\n"
        "def normalize_budget_category_snapshots(categories):\n"
        "    balance = 0\n"
        "    return [{'budgeted': 0, 'activity': 0, 'balance': balance}]\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert any(
        message.startswith(
            "Behavioral invariant failed: Split spending expands negative subtransactions "
            "[transaction aggregation: Split parent transactions must use negative subtransactions "
            "for spending totals.]:"
        )
        for message in messages
    )


def test_behavioral_invariant_manifest_is_required(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "scripts/harness/behavioral_invariants.toml").unlink()

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Behavioral invariant failed: Behavioral invariant manifest "
        "[harness metadata: Every behavioral fixture must have ownership metadata.]: "
        "Behavioral invariant manifest is missing: scripts/harness/behavioral_invariants.toml"
    ) in messages


def test_behavioral_invariant_manifest_requires_required_metadata(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "scripts/harness/behavioral_invariants.toml",
        "[[fixture]]\n"
        'id = "missing_metadata"\n'
        'label = "Missing metadata"\n'
        'owner_path = "src/domain/services/spending_aggregation.py"\n'
        'assertion = "split_spending_expands_negative_subtransactions"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert any(
        message.endswith(
            "Behavioral invariant fixture #1 is missing required metadata: "
            "risk_area, protected_rule"
        )
        for message in messages
    )


def test_behavioral_invariant_manifest_rejects_unknown_assertions(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "scripts/harness/behavioral_invariants.toml",
        "[[fixture]]\n"
        'id = "unknown_assertion"\n'
        'label = "Unknown assertion"\n'
        'risk_area = "test"\n'
        'protected_rule = "Unknown assertion should fail."\n'
        'owner_path = "src/domain/services/spending_aggregation.py"\n'
        'assertion = "does_not_exist"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert any(
        message.endswith(
            "Behavioral invariant assertion is unknown for unknown_assertion: does_not_exist"
        )
        for message in messages
    )


def test_behavioral_invariant_missing_evidence_path(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "scripts/harness/behavioral_invariants.toml",
        "[[fixture]]\n"
        'id = "missing_path"\n'
        'label = "Missing path"\n'
        'risk_area = "test"\n'
        'protected_rule = "Missing path should fail."\n'
        'owner_path = "src/domain/services/spending_aggregation.py"\n'
        'assertion = "split_spending_expands_negative_subtransactions"\n'
        "[[fixture.pytest_evidence]]\n"
        'path = "non_existent.py"\n'
        'snippet = "any"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert any(
        "Behavioral invariant pytest evidence path is missing: non_existent.py" in message
        for message in messages
    )


def test_behavioral_invariant_requires_pytest_and_doc_evidence(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "scripts/harness/behavioral_invariants.toml",
        "[[fixture]]\n"
        'id = "missing_evidence"\n'
        'label = "Missing evidence"\n'
        'risk_area = "test"\n'
        'protected_rule = "Evidence should be required."\n'
        'owner_path = "src/domain/services/spending_aggregation.py"\n'
        'assertion = "split_spending_expands_negative_subtransactions"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert any("pytest_evidence for missing_evidence is required" in message for message in messages)
    assert any("doc_evidence for missing_evidence is required" in message for message in messages)


def test_behavioral_invariant_missing_evidence_snippet(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "scripts/harness/behavioral_invariants.toml",
        "[[fixture]]\n"
        'id = "missing_snippet"\n'
        'label = "Missing snippet"\n'
        'risk_area = "test"\n'
        'protected_rule = "Missing snippet should fail."\n'
        'owner_path = "src/domain/services/spending_aggregation.py"\n'
        'assertion = "split_spending_expands_negative_subtransactions"\n'
        "[[fixture.pytest_evidence]]\n"
        'path = "src/domain/services/spending_aggregation.py"\n'
        'snippet = "missing_snippet_text"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert any(
        "Behavioral invariant pytest evidence snippet is missing: "
        "src/domain/services/spending_aggregation.py -> missing_snippet_text" in message
        for message in messages
    )
