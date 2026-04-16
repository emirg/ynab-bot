from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from domain.models.user import YNABBudget, YNABAccount, YNABCategory
from domain.models.split_config import SplitGroup


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


def build_split_panel_keyboard() -> InlineKeyboardMarkup:
    """Main panel for split configuration"""
    keyboard = [
        [InlineKeyboardButton("➕ Agregar grupo Splitwise", callback_data="split_add_group")],
        [InlineKeyboardButton("👁️ Ver configuración", callback_data="split_view")],
        [InlineKeyboardButton("🗑️ Quitar grupo Splitwise", callback_data="split_remove_group")],
        [InlineKeyboardButton("💳 Configurar cuenta compartida", callback_data="split_set_account")],
        [InlineKeyboardButton("❌ Quitar cuenta compartida", callback_data="split_remove_account")],
        [InlineKeyboardButton("👤 Gestionar aliases", callback_data="split_manage_aliases")],
    ]
    return InlineKeyboardMarkup(keyboard)


SPLIT_CATEGORIES_PAGE_SIZE = 8


def build_split_category_selection_keyboard(categories: List[YNABCategory], page: int = 0) -> InlineKeyboardMarkup:
    """Shows YNAB categories for selection as split groups, with pagination"""
    total = len(categories)
    start = page * SPLIT_CATEGORIES_PAGE_SIZE
    end = start + SPLIT_CATEGORIES_PAGE_SIZE
    page_categories = categories[start:end]

    keyboard = []
    for cat in page_categories:
        keyboard.append([InlineKeyboardButton(
            cat.name,
            callback_data=f"split_select_cat_{cat.id}"
        )])

    # Pagination row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"split_cat_page_{page - 1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"split_cat_page_{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="split_back")])
    return InlineKeyboardMarkup(keyboard)


def build_split_group_selection_keyboard(groups: List[SplitGroup], action: str) -> InlineKeyboardMarkup:
    """Shows existing split groups for removal or alias management"""
    keyboard = []
    for group in groups:
        keyboard.append([InlineKeyboardButton(
            group.category_name,
            callback_data=f"split_{action}_{group.category_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="split_back")])
    return InlineKeyboardMarkup(keyboard)


def build_split_account_selection_keyboard(accounts: List[YNABAccount]) -> InlineKeyboardMarkup:
    """Shows YNAB accounts for shared account selection"""
    keyboard = []
    # Limit to 10
    for acc in accounts[:10]:
        keyboard.append([InlineKeyboardButton(
            acc.name,
            callback_data=f"split_select_acc_{acc.id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="split_back")])
    return InlineKeyboardMarkup(keyboard)


def build_split_alias_action_keyboard(group: SplitGroup) -> InlineKeyboardMarkup:
    """For a specific group, shows options to add or remove aliases"""
    keyboard = [
        [InlineKeyboardButton("➕ Agregar alias", callback_data=f"split_add_alias_{group.category_id}")]
    ]
    
    # Current aliases as removable buttons
    # Using alias index in callback_data to avoid long alias names exceeding limit (64 bytes)
    for i, alias in enumerate(group.person_aliases):
        keyboard.append([InlineKeyboardButton(
            f"🗑️ Quitar {alias}", 
            callback_data=f"split_rma_{group.category_id}_{i}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="split_manage_aliases")])
    return InlineKeyboardMarkup(keyboard)


def build_split_ask_alias_keyboard(category_id: str) -> InlineKeyboardMarkup:
    """Asks if user wants to add an alias after adding a group"""
    keyboard = [
        [InlineKeyboardButton("✅ Sí, agregar alias", callback_data=f"split_ask_alias_{category_id}")],
        [InlineKeyboardButton("⏭️ Omitir", callback_data="split_skip_alias")]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Builds an inline keyboard for expense confirmation with Confirmar/Cancelar buttons."""
    keyboard = [
        [
            InlineKeyboardButton("Confirmar ✓", callback_data="confirm_expense"),
            InlineKeyboardButton("Cancelar ✗", callback_data="cancel_expense"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_monthly_summary_keyboard(view: str = "resumen") -> InlineKeyboardMarkup:
    """Build inline buttons for monthly /resumen drill-down views."""
    keyboard = []

    if view != "resumen":
        keyboard.append([InlineKeyboardButton("🔙 Volver al resumen", callback_data="resumen_mes_resumen")])

    if view != "categorias":
        keyboard.append([InlineKeyboardButton("📋 Ver categorías", callback_data="resumen_mes_categorias")])

    return InlineKeyboardMarkup(keyboard)
