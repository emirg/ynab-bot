from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from domain.models.user import YNABBudget, YNABAccount


def build_budget_selection_keyboard(budgets: List[YNABBudget]) -> InlineKeyboardMarkup:
    """Builds an inline keyboard for budget selection"""
    keyboard = []
    # Limit to 10 budgets to avoid too many buttons
    for i, budget in enumerate(budgets[:10], 1):
        keyboard.append([InlineKeyboardButton(
            f"{i}. {budget.name}", 
            callback_data=f"select_budget_{budget.id}"
        )])
    
    return InlineKeyboardMarkup(keyboard)


def build_account_selection_keyboard(accounts: List[YNABAccount]) -> InlineKeyboardMarkup:
    """Builds an inline keyboard for account selection"""
    keyboard = []
    # Limit to 10 accounts
    for i, account in enumerate(accounts[:10], 1):
        keyboard.append([InlineKeyboardButton(
            f"{i}. {account.name}", 
            callback_data=f"select_account_{account.id}"
        )])
    
    return InlineKeyboardMarkup(keyboard)


def budget_keyboard_to_dict(budgets: List[YNABBudget]) -> dict:
    """
    Returns a plain dict serializable to JSON for the Telegram Bot API.
    Used by the post-OAuth sync callback which doesn't use python-telegram-bot objects.
    """
    inline_keyboard = []
    for i, budget in enumerate(budgets[:10], 1):
        inline_keyboard.append([{
            "text": f"{i}. {budget.name}",
            "callback_data": f"select_budget_{budget.id}"
        }])
    
    return {"inline_keyboard": inline_keyboard}


def account_keyboard_to_dict(accounts: List[YNABAccount]) -> dict:
    """Returns a plain dict serializable to JSON for account selection"""
    inline_keyboard = []
    for i, account in enumerate(accounts[:10], 1):
        inline_keyboard.append([{
            "text": f"{i}. {account.name}",
            "callback_data": f"select_account_{account.id}"
        }])
    
    return {"inline_keyboard": inline_keyboard}
