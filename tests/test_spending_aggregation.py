from domain.services.spending_aggregation import extract_expense_entries


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


def test_extract_expense_entries_ignores_zero_sum_split_parents():
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

    assert entries == []
