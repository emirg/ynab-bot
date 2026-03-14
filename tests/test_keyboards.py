import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from presentation.telegram.keyboards import (
    build_budget_selection_keyboard,
    build_account_selection_keyboard,
    budget_keyboard_to_dict,
    account_keyboard_to_dict
)
from domain.models.user import YNABBudget, YNABAccount


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
