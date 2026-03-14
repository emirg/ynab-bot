import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from presentation.telegram.keyboards import (
    build_budget_selection_keyboard,
    build_account_selection_keyboard,
    budget_keyboard_to_dict,
    account_keyboard_to_dict,
    build_split_panel_keyboard,
    build_split_category_selection_keyboard,
    build_split_group_selection_keyboard,
    build_split_account_selection_keyboard,
    build_split_alias_action_keyboard,
    build_split_ask_alias_keyboard,
)
from domain.models.user import YNABBudget, YNABAccount, YNABCategory
from domain.models.split_config import SplitGroup


@pytest.fixture
def sample_budgets():
    return [
        YNABBudget(id=f"b{i}", name=f"Budget {i}", currency_format={})
        for i in range(1, 15)  # More than 10 to test limit
    ]


@pytest.fixture
def sample_accounts():
    return [
        YNABAccount(id=f"a{i}", name=f"Account {i}", type="checking")
        for i in range(1, 15)
    ]


def test_build_budget_selection_keyboard(sample_budgets):
    markup = build_budget_selection_keyboard(sample_budgets)
    assert isinstance(markup, InlineKeyboardMarkup)
    assert len(markup.inline_keyboard) == 10  # Limit to 10
    assert markup.inline_keyboard[0][0].text == "1. Budget 1"
    assert markup.inline_keyboard[0][0].callback_data == "select_budget_b1"


def test_build_account_selection_keyboard(sample_accounts):
    markup = build_account_selection_keyboard(sample_accounts)
    assert isinstance(markup, InlineKeyboardMarkup)
    assert len(markup.inline_keyboard) == 10
    assert markup.inline_keyboard[0][0].text == "1. Account 1"
    assert markup.inline_keyboard[0][0].callback_data == "select_account_a1"


def test_budget_keyboard_to_dict(sample_budgets):
    kb_dict = budget_keyboard_to_dict(sample_budgets)
    assert isinstance(kb_dict, dict)
    assert "inline_keyboard" in kb_dict
    assert len(kb_dict["inline_keyboard"]) == 10
    assert kb_dict["inline_keyboard"][0][0]["text"] == "1. Budget 1"
    assert kb_dict["inline_keyboard"][0][0]["callback_data"] == "select_budget_b1"


def test_account_keyboard_to_dict(sample_accounts):
    kb_dict = account_keyboard_to_dict(sample_accounts)
    assert isinstance(kb_dict, dict)
    assert "inline_keyboard" in kb_dict
    assert len(kb_dict["inline_keyboard"]) == 10
    assert kb_dict["inline_keyboard"][0][0]["text"] == "1. Account 1"
    assert kb_dict["inline_keyboard"][0][0]["callback_data"] == "select_account_a1"


def test_empty_keyboards():
    assert len(build_budget_selection_keyboard([]).inline_keyboard) == 0
    assert len(build_account_selection_keyboard([]).inline_keyboard) == 0
    assert len(budget_keyboard_to_dict([])["inline_keyboard"]) == 0
    assert len(account_keyboard_to_dict([])["inline_keyboard"]) == 0


# ---------------------------------------------------------------------------
# Split configuration keyboards
# ---------------------------------------------------------------------------

def test_build_split_panel_keyboard():
    markup = build_split_panel_keyboard()
    assert isinstance(markup, InlineKeyboardMarkup)
    assert len(markup.inline_keyboard) == 6
    assert markup.inline_keyboard[0][0].callback_data == "split_add_group"
    assert markup.inline_keyboard[5][0].callback_data == "split_manage_aliases"


def test_build_split_category_selection_keyboard_first_page():
    cats = [YNABCategory(id=f"c{i}", name=f"Cat {i}", group_name="G", full_name=f"G: Cat {i}") for i in range(20)]
    markup = build_split_category_selection_keyboard(cats, page=0)
    # 8 cats + 1 nav row (next) + 1 back = 10 rows
    assert len(markup.inline_keyboard) == 10
    assert markup.inline_keyboard[0][0].callback_data == "split_select_cat_c0"
    assert markup.inline_keyboard[7][0].callback_data == "split_select_cat_c7"
    # Nav row: only "Siguiente"
    assert len(markup.inline_keyboard[8]) == 1
    assert markup.inline_keyboard[8][0].callback_data == "split_cat_page_1"
    assert markup.inline_keyboard[9][0].callback_data == "split_back"


def test_build_split_category_selection_keyboard_middle_page():
    cats = [YNABCategory(id=f"c{i}", name=f"Cat {i}", group_name="G", full_name=f"G: Cat {i}") for i in range(25)]
    markup = build_split_category_selection_keyboard(cats, page=1)
    # 8 cats + 1 nav row (prev + next) + 1 back = 10 rows
    assert len(markup.inline_keyboard) == 10
    assert markup.inline_keyboard[0][0].callback_data == "split_select_cat_c8"
    # Nav row: both buttons
    nav_row = markup.inline_keyboard[8]
    assert len(nav_row) == 2
    assert nav_row[0].callback_data == "split_cat_page_0"
    assert nav_row[1].callback_data == "split_cat_page_2"


def test_build_split_category_selection_keyboard_last_page():
    cats = [YNABCategory(id=f"c{i}", name=f"Cat {i}", group_name="G", full_name=f"G: Cat {i}") for i in range(20)]
    markup = build_split_category_selection_keyboard(cats, page=2)
    # 4 remaining cats + 1 nav row (prev only) + 1 back = 6 rows
    assert len(markup.inline_keyboard) == 6
    assert markup.inline_keyboard[0][0].callback_data == "split_select_cat_c16"
    assert markup.inline_keyboard[3][0].callback_data == "split_select_cat_c19"
    nav_row = markup.inline_keyboard[4]
    assert len(nav_row) == 1
    assert nav_row[0].callback_data == "split_cat_page_1"


def test_build_split_category_selection_keyboard_few_categories():
    """No pagination when categories fit in one page"""
    cats = [YNABCategory(id=f"c{i}", name=f"Cat {i}", group_name="G", full_name=f"G: Cat {i}") for i in range(5)]
    markup = build_split_category_selection_keyboard(cats)
    # 5 cats + 1 back = 6 rows, no nav
    assert len(markup.inline_keyboard) == 6
    assert markup.inline_keyboard[5][0].callback_data == "split_back"


def test_build_split_group_selection_keyboard():
    groups = [
        SplitGroup(id=1, telegram_id=1, category_id="cat1", category_name="G1", person_aliases=[]),
        SplitGroup(id=2, telegram_id=1, category_id="cat2", category_name="G2", person_aliases=[])
    ]
    markup = build_split_group_selection_keyboard(groups, "rm")
    assert len(markup.inline_keyboard) == 3  # 2 groups + 1 back
    assert markup.inline_keyboard[0][0].callback_data == "split_rm_cat1"
    assert markup.inline_keyboard[2][0].callback_data == "split_back"


def test_build_split_account_selection_keyboard():
    accs = [YNABAccount(id=f"a{i}", name=f"Acc {i}", type="checking") for i in range(15)]
    markup = build_split_account_selection_keyboard(accs)
    assert len(markup.inline_keyboard) == 11  # 10 accs + 1 back
    assert markup.inline_keyboard[0][0].callback_data == "split_select_acc_a0"


def test_build_split_alias_action_keyboard():
    group = SplitGroup(id=1, telegram_id=1, category_id="uuid-1", category_name="G1", person_aliases=["A1", "A2"])
    markup = build_split_alias_action_keyboard(group)
    assert len(markup.inline_keyboard) == 4  # 1 add + 2 current + 1 back
    assert markup.inline_keyboard[0][0].callback_data == "split_add_alias_uuid-1"
    assert markup.inline_keyboard[1][0].callback_data == "split_rma_uuid-1_0"
    assert markup.inline_keyboard[2][0].callback_data == "split_rma_uuid-1_1"
    assert markup.inline_keyboard[3][0].callback_data == "split_manage_aliases"


def test_build_split_ask_alias_keyboard():
    markup = build_split_ask_alias_keyboard("cat-id")
    assert len(markup.inline_keyboard) == 2
    assert markup.inline_keyboard[0][0].callback_data == "split_ask_alias_cat-id"
    assert markup.inline_keyboard[1][0].callback_data == "split_skip_alias"

