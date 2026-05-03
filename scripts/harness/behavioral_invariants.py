from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
import tomllib
from types import ModuleType
from typing import Any, Callable
from uuid import uuid4

MANIFEST_PATH = "scripts/harness/behavioral_invariants.toml"
REQUIRED_MANIFEST_FIELDS = (
    "id",
    "label",
    "risk_area",
    "protected_rule",
    "owner_path",
    "assertion",
)


@dataclass(frozen=True)
class Evidence:
    path: str
    snippet: str


@dataclass(frozen=True)
class BehaviorFixture:
    fixture_id: str
    label: str
    risk_area: str
    protected_rule: str
    owner_path: str
    assertion: Callable[[Path], None] | None
    pytest_evidence: list[Evidence]
    doc_evidence: list[Evidence]


@dataclass(frozen=True)
class BehaviorResult:
    fixture_id: str
    label: str
    risk_area: str
    protected_rule: str
    passed: bool
    message: str
    path: str | None = None


class FakeYNABRepository:
    def __init__(self, transactions: dict[str, dict]):
        self.transactions = transactions

    def get_transaction_by_id(self, budget_id: str, transaction_id: str) -> dict | None:
        return self.transactions.get(transaction_id)


def run_behavioral_invariants(root: Path | str) -> list[BehaviorResult]:
    repo_root = Path(root)
    fixtures, manifest_errors = load_behavior_fixtures(repo_root)

    results: list[BehaviorResult] = []
    results.extend(manifest_errors)

    # If we have manifest errors for a fixture, we might still want to run its assertion
    # but the load_behavior_fixtures currently returns fixtures ONLY if they pass basic manifest validation.
    # Evidence validation is now part of manifest_errors.

    for fixture in fixtures:
        if fixture.assertion is None:
            continue
        try:
            fixture.assertion(repo_root)
        except AssertionError as exc:
            results.append(
                _fixture_result(fixture, False, str(exc) or "Assertion failed")
            )
        except Exception as exc:
            results.append(
                _fixture_result(fixture, False, f"{exc.__class__.__name__}: {exc}")
            )
        else:
            results.append(_fixture_result(fixture, True, "Behavioral invariant holds"))
    return results


def load_behavior_fixtures(root: Path) -> tuple[list[BehaviorFixture], list[BehaviorResult]]:
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.is_file():
        return [], [_manifest_error(f"Behavioral invariant manifest is missing: {MANIFEST_PATH}")]

    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [], [_manifest_error(f"Behavioral invariant manifest is invalid TOML: {exc}")]

    entries = manifest.get("fixture")
    if not isinstance(entries, list):
        return [], [_manifest_error("Behavioral invariant manifest must define [[fixture]] entries")]

    assertions = _assertion_registry()
    seen_ids: set[str] = set()
    fixtures: list[BehaviorFixture] = []
    errors: list[BehaviorResult] = []

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(_manifest_error(f"Behavioral invariant fixture #{index} must be a table"))
            continue

        missing = [
            field
            for field in REQUIRED_MANIFEST_FIELDS
            if not isinstance(entry.get(field), str) or not entry[field].strip()
        ]
        if missing:
            errors.append(
                _manifest_error(
                    f"Behavioral invariant fixture #{index} is missing required metadata: "
                    f"{', '.join(missing)}"
                )
            )
            continue

        fixture_id = entry["id"].strip()
        label = entry["label"].strip()
        risk_area = entry["risk_area"].strip()
        protected_rule = entry["protected_rule"].strip()
        owner_path = entry["owner_path"].strip()
        assertion_name = entry["assertion"].strip()

        if fixture_id in seen_ids:
            errors.append(_manifest_error(f"Behavioral invariant fixture id is duplicated: {fixture_id}"))
            continue
        seen_ids.add(fixture_id)

        if not (root / owner_path).is_file():
            errors.append(
                _manifest_error(
                    f"Behavioral invariant owner path is missing for {fixture_id}: {owner_path}",
                    owner_path,
                )
            )
            continue

        assertion = assertions.get(assertion_name)
        if assertion is None:
            errors.append(
                _manifest_error(
                    f"Behavioral invariant assertion is unknown for {fixture_id}: {assertion_name}",
                    MANIFEST_PATH,
                )
            )
            continue

        pytest_evidence_raw = entry.get("pytest_evidence", [])
        doc_evidence_raw = entry.get("doc_evidence", [])

        if "pytest_evidence" not in entry:
            errors.append(_manifest_error(f"pytest_evidence for {fixture_id} is required"))
        if "doc_evidence" not in entry:
            errors.append(_manifest_error(f"doc_evidence for {fixture_id} is required"))

        if not isinstance(pytest_evidence_raw, list):
            errors.append(_manifest_error(f"pytest_evidence for {fixture_id} must be a list"))
            pytest_evidence_raw = []
        if not isinstance(doc_evidence_raw, list):
            errors.append(_manifest_error(f"doc_evidence for {fixture_id} must be a list"))
            doc_evidence_raw = []

        pytest_evidence = []
        for e in pytest_evidence_raw:
            if isinstance(e, dict) and "path" in e and "snippet" in e:
                pytest_evidence.append(Evidence(path=e["path"], snippet=e["snippet"]))
            else:
                errors.append(_manifest_error(f"Invalid pytest_evidence entry for {fixture_id}"))

        doc_evidence = []
        for e in doc_evidence_raw:
            if isinstance(e, dict) and "path" in e and "snippet" in e:
                doc_evidence.append(Evidence(path=e["path"], snippet=e["snippet"]))
            else:
                errors.append(_manifest_error(f"Invalid doc_evidence entry for {fixture_id}"))

        fixture = BehaviorFixture(
            fixture_id=fixture_id,
            label=label,
            risk_area=risk_area,
            protected_rule=protected_rule,
            owner_path=owner_path,
            assertion=assertion,
            pytest_evidence=pytest_evidence,
            doc_evidence=doc_evidence,
        )

        # Validate evidence
        evidence_errors = _validate_fixture_evidence(root, fixture)
        if evidence_errors:
            errors.extend(evidence_errors)
        else:
            fixtures.append(fixture)

    return fixtures, errors


def _validate_fixture_evidence(root: Path, fixture: BehaviorFixture) -> list[BehaviorResult]:
    errors = []
    
    for ev in fixture.pytest_evidence:
        err = _validate_evidence_item(root, fixture, ev, "pytest")
        if err:
            errors.append(err)
            
    for ev in fixture.doc_evidence:
        err = _validate_evidence_item(root, fixture, ev, "documentation")
        if err:
            errors.append(err)
            
    return errors


def _validate_evidence_item(root: Path, fixture: BehaviorFixture, ev: Evidence, type_label: str) -> BehaviorResult | None:
    path = root / ev.path
    if not path.is_file():
        return _fixture_result(
            fixture, 
            False, 
            f"Behavioral invariant {type_label} evidence path is missing: {ev.path}"
        )
    
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return _fixture_result(
            fixture,
            False,
            f"Behavioral invariant {type_label} evidence path could not be read: {ev.path} ({exc})"
        )

    if ev.snippet not in content:
        return _fixture_result(
            fixture,
            False,
            f"Behavioral invariant {type_label} evidence snippet is missing: {ev.path} -> {ev.snippet}"
        )
    
    return None


def _assertion_registry() -> dict[str, Callable[[Path], None]]:
    return {
        "split_spending_expands_negative_subtransactions": _assert_split_spending_expands_negative_subtransactions,
        "zero_sum_shared_split_counts_negative_leg": _assert_zero_sum_shared_split_counts_negative_leg,
        "net_spending_offsets_categorized_inflows": _assert_net_spending_offsets_categorized_inflows,
        "budget_snapshots_preserve_balance": _assert_budget_snapshots_preserve_balance,
        "edit_reconciliation_trusts_live_identity": _assert_edit_reconciliation_trusts_live_identity,
        "undo_reconciliation_blocks_stale_recent_reference": _assert_undo_reconciliation_blocks_stale_recent_reference,
        "shared_expense_construction_preserves_zero_sum": _assert_shared_expense_construction_preserves_zero_sum,
        "splitwise_responsibility_matrix_controls_ynab_shape": _assert_splitwise_responsibility_matrix_controls_ynab_shape,
        "account_balance_reads_from_account_fields": _assert_account_balance_reads_from_account_fields,
    }


def _fixture_result(fixture: BehaviorFixture, passed: bool, message: str) -> BehaviorResult:
    return BehaviorResult(
        fixture_id=fixture.fixture_id,
        label=fixture.label,
        risk_area=fixture.risk_area,
        protected_rule=fixture.protected_rule,
        passed=passed,
        message=message,
        path=fixture.owner_path,
    )


def _manifest_error(message: str, path: str | None = MANIFEST_PATH) -> BehaviorResult:
    return BehaviorResult(
        fixture_id="manifest",
        label="Behavioral invariant manifest",
        risk_area="harness metadata",
        protected_rule="Every behavioral fixture must have ownership metadata.",
        passed=False,
        message=message,
        path=path,
    )


def _assert_split_spending_expands_negative_subtransactions(root: Path) -> None:
    module = _load_spending_module(root)
    total_spent, category_totals = module.summarize_transaction_spending(
        [
            {
                "amount": -100_000,
                "date": "2026-04-12",
                "category_name": "Split (Multiple Categories)",
                "subtransactions": [
                    {"amount": -70_000, "category_name": "Groceries"},
                    {"amount": -30_000, "category_name": "Meal delivery"},
                ],
            },
            {"amount": -20_000, "date": "2026-04-12", "category_name": "Groceries"},
        ]
    )

    assert total_spent == 120_000, f"expected total 120000, got {total_spent}"
    assert category_totals == {
        "Groceries": 90_000,
        "Meal delivery": 30_000,
    }, f"unexpected category totals: {category_totals!r}"


def _assert_zero_sum_shared_split_counts_negative_leg(root: Path) -> None:
    module = _load_spending_module(root)
    total_spent, category_totals = module.summarize_transaction_spending(
        [
            {
                "amount": 0,
                "date": "2026-04-12",
                "category_name": "Split (Multiple Categories)",
                "subtransactions": [
                    {"amount": -40_000, "category_name": "Meal delivery"},
                    {"amount": 40_000, "category_name": "Splitwise"},
                ],
            }
        ]
    )

    assert total_spent == 40_000, f"expected total 40000, got {total_spent}"
    assert category_totals == {
        "Meal delivery": 40_000,
    }, f"unexpected category totals: {category_totals!r}"


def _assert_net_spending_offsets_categorized_inflows(root: Path) -> None:
    module = _load_spending_module(root)
    total_spent, category_totals = module.summarize_transaction_net_spending(
        [
            {
                "amount": -80_000,
                "date": "2026-04-12",
                "category_name": "Split (Multiple Categories)",
                "subtransactions": [
                    {
                        "amount": -50_000,
                        "category_id": "cat-meal",
                        "category_name": "Meal delivery",
                    },
                    {
                        "amount": -30_000,
                        "category_id": "cat-split",
                        "category_name": "Splitwise",
                    },
                ],
            },
            {
                "amount": 60_000,
                "date": "2026-04-13",
                "category_id": "cat-split",
                "category_name": "Splitwise",
            },
            {
                "amount": 500_000,
                "date": "2026-04-14",
                "category_id": "cat-income",
                "category_name": "Inflow: Ready to Assign",
            },
        ]
    )

    assert total_spent == 20_000, f"expected net total 20000, got {total_spent}"
    assert category_totals == {
        "Meal delivery": 50_000,
    }, f"unexpected net category totals: {category_totals!r}"


def _assert_budget_snapshots_preserve_balance(root: Path) -> None:
    module = _load_spending_module(root)
    snapshots = module.normalize_budget_category_snapshots(
        [
            {
                "name": "Comida",
                "budgeted": 100_000,
                "activity": -20_000,
                "balance": 80_000,
            },
            {
                "name": "Oculta",
                "budgeted": 50_000,
                "activity": -10_000,
                "balance": 40_000,
                "hidden": True,
            },
            {
                "name": "Eliminada",
                "budgeted": 50_000,
                "activity": -10_000,
                "balance": 40_000,
                "deleted": True,
            },
            {
                "name": "Sin movimiento",
                "budgeted": 0,
                "activity": 0,
                "balance": 0,
            },
        ]
    )

    assert snapshots == [
        {
            "name": "Comida",
            "budgeted": 100_000,
            "activity": -20_000,
            "balance": 80_000,
        }
    ], f"unexpected category snapshots: {snapshots!r}"


def _assert_edit_reconciliation_trusts_live_identity(root: Path) -> None:
    service = _new_expense_service(root)
    live_transaction = {
        "id": "txn-edit-1",
        "amount": -30_000_000,
        "payee_name": "Live Payee",
        "category_id": "cat-live",
    }
    cached_transaction = {
        "ynab_transaction_id": "txn-edit-1",
        "amount": 25_000,
        "payee": "Cached Payee",
        "category_id": "cat-cached",
    }

    result, error = service._get_live_transaction_state_for_edit(
        FakeYNABRepository({"txn-edit-1": live_transaction}),
        "budget-1",
        cached_transaction,
    )

    assert error is None, f"expected edit reconciliation to pass, got {error!r}"
    assert result == live_transaction, f"expected live transaction, got {result!r}"


def _assert_undo_reconciliation_blocks_stale_recent_reference(root: Path) -> None:
    service = _new_expense_service(root)
    live_transaction = {
        "id": "txn-undo-1",
        "amount": -30_000_000,
        "payee_name": "Cached Payee",
        "category_id": "cat-cached",
    }
    cached_transaction = {
        "ynab_transaction_id": "txn-undo-1",
        "amount": 25_000,
        "payee": "Cached Payee",
        "category_id": "cat-cached",
    }

    result, error = service._get_live_transaction_state(
        FakeYNABRepository({"txn-undo-1": live_transaction}),
        "budget-1",
        cached_transaction,
    )

    assert result is None, f"expected stale undo reference to return no transaction, got {result!r}"
    assert error == "ynab_transaction_stale", f"expected stale error, got {error!r}"


def _assert_shared_expense_construction_preserves_zero_sum(root: Path) -> None:
    from decimal import Decimal

    expense_cls = _load_expense_class(root)
    # Other-paid split (zero-sum)
    expense = expense_cls(
        amount=Decimal("60.0"),
        payee="Dinner",
        memo="Split",
        is_split=True,
        payer="other",
        split_category_id="00000000-0000-0000-0000-000000000001",
        split_proportion=Decimal("0.5"),
    )

    result = expense.to_ynab_format("budget-1", "acct-1")
    txn = result["transaction"]

    assert txn["amount"] == 0, f"expected zero-sum transaction amount, got {txn['amount']}"
    assert len(txn["subtransactions"]) == 2, "expected 2 subtransactions"
    assert (
        txn["subtransactions"][0]["amount"] == -30000
    ), f"expected user share -30000, got {txn['subtransactions'][0]['amount']}"
    assert (
        txn["subtransactions"][1]["amount"] == 30000
    ), f"expected splitwise share 30000, got {txn['subtransactions'][1]['amount']}"


def _assert_splitwise_responsibility_matrix_controls_ynab_shape(root: Path) -> None:
    from decimal import Decimal

    expense_cls = _load_expense_class(root)
    real_category_id = "00000000-0000-0000-0000-000000000010"
    split_category_id = "00000000-0000-0000-0000-000000000020"

    def build_expense(
        *,
        amount: str,
        payer: str,
        user_share: str,
        other_share: str,
    ) -> Any:
        return expense_cls(
            amount=Decimal(amount),
            payee="Carulla",
            memo="Splitwise matrix",
            category_id=real_category_id,
            category_name="Groceries",
            is_split=True,
            payer=payer,
            split_category_id=split_category_id,
            split_category_name="Gastos Splitwise",
            split_user_share_amount=Decimal(user_share),
            split_other_share_amount=Decimal(other_share),
        )

    user_paid_half = build_expense(
        amount="200.0",
        payer="user",
        user_share="100.0",
        other_share="100.0",
    ).to_ynab_format("budget-1", "rappi-card")["transaction"]
    assert user_paid_half["account_id"] == "rappi-card"
    assert user_paid_half["amount"] == -200000
    assert "category_id" not in user_paid_half
    assert user_paid_half["subtransactions"] == [
        {"amount": -100000, "category_id": real_category_id},
        {"amount": -100000, "category_id": split_category_id},
    ]

    other_paid_half = build_expense(
        amount="200.0",
        payer="other",
        user_share="100.0",
        other_share="100.0",
    ).to_ynab_format("budget-1", "shared-account")["transaction"]
    assert other_paid_half["account_id"] == "shared-account"
    assert other_paid_half["amount"] == 0
    assert other_paid_half["subtransactions"] == [
        {"amount": -100000, "category_id": real_category_id},
        {"amount": 100000, "category_id": split_category_id},
    ]

    user_paid_for_other = build_expense(
        amount="100.0",
        payer="user",
        user_share="0.0",
        other_share="100.0",
    ).to_ynab_format("budget-1", "rappi-card")["transaction"]
    assert user_paid_for_other["account_id"] == "rappi-card"
    assert user_paid_for_other["amount"] == -100000
    assert user_paid_for_other["category_id"] == split_category_id
    assert "subtransactions" not in user_paid_for_other

    other_paid_for_user = build_expense(
        amount="200.0",
        payer="other",
        user_share="200.0",
        other_share="0.0",
    ).to_ynab_format("budget-1", "shared-account")["transaction"]
    assert other_paid_for_user["account_id"] == "shared-account"
    assert other_paid_for_user["amount"] == 0
    assert other_paid_for_user["subtransactions"] == [
        {"amount": -200000, "category_id": real_category_id},
        {"amount": 200000, "category_id": split_category_id},
    ]


def _assert_account_balance_reads_from_account_fields(root: Path) -> None:
    service = _load_budget_query_service(root)
    from dataclasses import dataclass

    @dataclass
    class MockAccount:
        name: str
        type: str
        balance: int
        cleared_balance: int
        uncleared_balance: int
        deleted: bool = False
        closed: bool = False

    accounts = [
        MockAccount(
            name="Nu Card",
            type="checking",
            balance=-500000,
            cleared_balance=-400000,
            uncleared_balance=-100000,
        )
    ]

    result = service.execute_query(
        query_type="account_balance",
        query_target="Nu Card",
        categories=[],
        accounts=accounts,
    )

    assert result.success, f"expected query success, got {result.error_message}"
    data = result.data
    assert data["balance"] == -500000, f"expected balance -500000, got {data['balance']}"
    assert (
        data["cleared_balance"] == -400000
    ), f"expected cleared_balance -400000, got {data['cleared_balance']}"


def _load_spending_module(root: Path) -> ModuleType:
    return _load_module_from_path(
        root,
        "src/domain/services/spending_aggregation.py",
        "harness_behavioral_spending_aggregation",
    )


def _new_expense_service(root: Path) -> Any:
    module = _load_module_from_path(
        root,
        "src/application/services/expense_service.py",
        "harness_behavioral_expense_service",
    )
    return object.__new__(module.ExpenseService)


def _load_expense_class(root: Path) -> Any:
    module = _load_module_from_path(
        root,
        "src/domain/models/expense.py",
        "harness_behavioral_expense_model",
    )
    return module.Expense


def _load_budget_query_service(root: Path) -> Any:
    module = _load_module_from_path(
        root,
        "src/application/services/budget_query_service.py",
        "harness_behavioral_budget_query_service",
    )
    return module.BudgetQueryService()


def _load_module_from_path(root: Path, relative_path: str, prefix: str) -> ModuleType:
    path = root / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)

    module_name = f"{prefix}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {relative_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    with _source_path(root):
        spec.loader.exec_module(module)
    return module


@contextmanager
def _source_path(root: Path):
    source_path = str(root / "src")
    sys.path.insert(0, source_path)
    try:
        yield
    finally:
        try:
            sys.path.remove(source_path)
        except ValueError:
            pass
