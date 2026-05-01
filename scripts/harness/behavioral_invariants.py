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
class BehaviorFixture:
    fixture_id: str
    label: str
    risk_area: str
    protected_rule: str
    owner_path: str
    assertion: Callable[[Path], None] | None


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

        fixtures.append(
            BehaviorFixture(
                fixture_id=fixture_id,
                label=label,
                risk_area=risk_area,
                protected_rule=protected_rule,
                owner_path=owner_path,
                assertion=assertion,
            )
        )

    return fixtures, errors


def _assertion_registry() -> dict[str, Callable[[Path], None]]:
    return {
        "split_spending_expands_negative_subtransactions": _assert_split_spending_expands_negative_subtransactions,
        "zero_sum_shared_split_counts_negative_leg": _assert_zero_sum_shared_split_counts_negative_leg,
        "net_spending_offsets_categorized_inflows": _assert_net_spending_offsets_categorized_inflows,
        "budget_snapshots_preserve_balance": _assert_budget_snapshots_preserve_balance,
        "edit_reconciliation_trusts_live_identity": _assert_edit_reconciliation_trusts_live_identity,
        "undo_reconciliation_blocks_stale_recent_reference": _assert_undo_reconciliation_blocks_stale_recent_reference,
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


def _load_module_from_path(root: Path, relative_path: str, prefix: str) -> ModuleType:
    path = root / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)

    module_name = f"{prefix}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {relative_path}")

    module = importlib.util.module_from_spec(spec)
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
