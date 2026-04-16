from domain.models.user import YNABCategory
from domain.services.spending_aggregation import (
    extract_expense_entries,
    normalize_budget_category_snapshots,
    summarize_transaction_net_spending,
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


def test_extract_expense_entries_ignores_transfer_transactions():
    entries = extract_expense_entries(
        [
            {
                "amount": -250_000,
                "date": "2026-04-12",
                "category_name": None,
                "transfer_account_id": "acct-2",
                "transfer_transaction_id": "txn-2",
            }
        ]
    )

    assert entries == []


def test_summarize_transaction_spending_ignores_transfer_transactions():
    total_spent, category_totals = summarize_transaction_spending(
        [
            {
                "amount": -250_000,
                "date": "2026-04-12",
                "category_name": None,
                "transfer_account_id": "acct-2",
                "transfer_transaction_id": "txn-2",
            },
            {"amount": -40_000, "date": "2026-04-12", "category_name": "Meal delivery"},
        ]
    )

    assert total_spent == 40_000
    assert category_totals == {"Meal delivery": 40_000}


def test_summarize_transaction_net_spending_offsets_category_inflows():
    total_spent, category_totals = summarize_transaction_net_spending(
        [
            {"amount": -120_000, "date": "2026-04-12", "category_name": "Meal delivery"},
            {
                "amount": 40_000,
                "date": "2026-04-12",
                "category_id": "cat-refunds",
                "category_name": "Reembolsos",
            },
        ]
    )

    assert total_spent == 80_000
    assert category_totals == {"Meal delivery": 120_000}


def test_summarize_transaction_net_spending_ignores_ready_to_assign_inflows():
    total_spent, category_totals = summarize_transaction_net_spending(
        [
            {"amount": -120_000, "date": "2026-04-12", "category_name": "Meal delivery"},
            {
                "amount": 500_000,
                "date": "2026-04-12",
                "category_id": "cat-income",
                "category_name": "Inflow: Ready to Assign",
            },
        ]
    )

    assert total_spent == 120_000
    assert category_totals == {"Meal delivery": 120_000}


def test_summarize_transaction_net_spending_nets_split_tracking_inflows_against_month_total():
    total_spent, category_totals = summarize_transaction_net_spending(
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
        ]
    )

    assert total_spent == 20_000
    assert category_totals == {"Meal delivery": 50_000}


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
