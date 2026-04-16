from domain.models.user import YNABCategory
from domain.services.spending_aggregation import (
    extract_expense_entries,
    normalize_budget_category_snapshots,
    summarize_transaction_spending,
)


def test_extract_expense_entries_expands_negative_split_subtransactions():
    entries = extract_expense_entries(
        [
            {
                "amount": -100_000,
                "date": "2026-04-12",
                "category_name": "Split (Multiple Categories)",
                "subtransactions": [
                    {"amount": -70_000, "category_name": "Groceries"},
                    {"amount": -30_000, "category_name": "Meal delivery"},
                ],
            }
        ]
    )

    assert entries == [
        {"amount": -70_000, "category_name": "Groceries", "date": "2026-04-12"},
        {"amount": -30_000, "category_name": "Meal delivery", "date": "2026-04-12"},
    ]


def test_extract_expense_entries_keeps_negative_leg_from_zero_sum_split_parents():
    entries = extract_expense_entries(
        [
            {
                "amount": 0,
                "date": "2026-04-12",
                "category_name": "Split (Multiple Categories)",
                "subtransactions": [
                    {"amount": -40_000, "category_name": "Meal delivery"},
                    {"amount": 40_000, "category_name": "Reembolsos"},
                ],
            }
        ]
    )

    assert entries == [
        {"amount": -40_000, "category_name": "Meal delivery", "date": "2026-04-12"},
    ]


def test_summarize_transaction_spending_counts_zero_sum_shared_split_expenses():
    total_spent, category_totals = summarize_transaction_spending(
        [
            {
                "amount": 0,
                "date": "2026-04-12",
                "category_name": "Split (Multiple Categories)",
                "subtransactions": [
                    {"amount": -40_000, "category_name": "Meal delivery"},
                    {"amount": 40_000, "category_name": "Reembolsos"},
                ],
            }
        ]
    )

    assert total_spent == 40_000
    assert category_totals == {"Meal delivery": 40_000}


def test_summarize_transaction_spending_uses_expanded_split_entries():
    total_spent, category_totals = summarize_transaction_spending(
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

    assert total_spent == 120_000
    assert category_totals == {"Groceries": 90_000, "Meal delivery": 30_000}


def test_normalize_budget_category_snapshots_filters_inactive_hidden_and_deleted():
    snapshots = normalize_budget_category_snapshots(
        [
            YNABCategory(
                id="1",
                name="Comida",
                group_name="Casa",
                full_name="Casa -> Comida",
                budgeted=100_000,
                activity=-20_000,
                balance=80_000,
            ),
            YNABCategory(
                id="2",
                name="Oculta",
                group_name="Casa",
                full_name="Casa -> Oculta",
                budgeted=50_000,
                activity=-10_000,
                balance=40_000,
                hidden=True,
            ),
            YNABCategory(
                id="3",
                name="Sin movimiento",
                group_name="Casa",
                full_name="Casa -> Sin movimiento",
                budgeted=0,
                activity=0,
                balance=0,
            ),
        ]
    )

    assert snapshots == [
        {
            "name": "Comida",
            "budgeted": 100_000,
            "activity": -20_000,
            "balance": 80_000,
        }
    ]
