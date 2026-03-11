import logging
import re
from typing import List, Optional

from domain.models.budget_query import BudgetQueryResult
from domain.models.user import YNABCategory, YNABAccount

logger = logging.getLogger(__name__)

_SPECIAL_CHARS_PATTERN = re.compile(r'[^\w\s]', re.UNICODE)


class BudgetQueryService:
    """Service for executing budget queries against YNAB data."""

    def execute_query(
        self,
        query_type: str,
        query_target: Optional[str],
        categories: List[YNABCategory],
        accounts: List[YNABAccount],
    ) -> BudgetQueryResult:
        if query_type == 'category_balance':
            return self._query_category_balance(categories, query_target)
        elif query_type == 'account_balance':
            return self._query_account_balance(accounts, query_target)
        elif query_type == 'budget_summary':
            return self._query_budget_summary(categories)
        else:
            return BudgetQueryResult.error_result(query_type, f"Tipo de consulta no soportado: {query_type}")

    def _query_category_balance(self, categories: List[YNABCategory], target_name: Optional[str]) -> BudgetQueryResult:
        if not target_name:
            return BudgetQueryResult.error_result('category_balance', 'No se especificó una categoría.')

        category = self._find_category(categories, target_name)
        if not category:
            return BudgetQueryResult.error_result(
                'category_balance',
                f"No encontré la categoría \"{target_name}\". Intenta con el nombre exacto.",
            )

        return BudgetQueryResult.success_result('category_balance', {
            'name': category.name,
            'group_name': category.group_name,
            'budgeted': category.budgeted,
            'activity': category.activity,
            'balance': category.balance,
        })

    def _query_account_balance(self, accounts: List[YNABAccount], target_name: Optional[str]) -> BudgetQueryResult:
        if not target_name:
            return BudgetQueryResult.error_result('account_balance', 'No se especificó una cuenta.')

        account = self._find_account(accounts, target_name)
        if not account:
            return BudgetQueryResult.error_result(
                'account_balance',
                f"No encontré la cuenta \"{target_name}\". Intenta con el nombre exacto.",
            )

        return BudgetQueryResult.success_result('account_balance', {
            'name': account.name,
            'type': account.type,
            'balance': account.balance,
            'cleared_balance': account.cleared_balance,
            'uncleared_balance': account.uncleared_balance,
        })

    def _query_budget_summary(self, categories: List[YNABCategory]) -> BudgetQueryResult:
        active = [c for c in categories if not c.deleted and not c.hidden]

        total_budgeted = sum(c.budgeted for c in active)
        total_activity = sum(c.activity for c in active)
        total_balance = sum(c.balance for c in active)

        # Top categories by spending (activity is negative for expenses)
        by_spending = sorted(active, key=lambda c: c.activity)
        top_spending = [
            {'name': c.name, 'activity': c.activity, 'balance': c.balance}
            for c in by_spending[:5]
            if c.activity < 0
        ]

        return BudgetQueryResult.success_result('budget_summary', {
            'total_budgeted': total_budgeted,
            'total_activity': total_activity,
            'total_balance': total_balance,
            'category_count': len(active),
            'top_spending': top_spending,
        })

    def _find_category(self, categories: List[YNABCategory], name: str) -> Optional[YNABCategory]:
        """Find category by name with fuzzy matching (exact → case-insensitive → partial → clean)."""
        name = name.strip()
        active = [c for c in categories if not c.deleted and not c.hidden]

        # 1. Exact match
        for c in active:
            if c.name == name or c.full_name == name:
                return c

        # 2. Case-insensitive
        name_lower = name.lower()
        for c in active:
            if c.name.lower() == name_lower or c.full_name.lower() == name_lower:
                return c

        # 3. Match without special chars/emojis (Clean Match)
        name_clean = _SPECIAL_CHARS_PATTERN.sub('', name).strip().lower()
        if name_clean:
            for c in active:
                c_clean = _SPECIAL_CHARS_PATTERN.sub('', c.name).strip().lower()
                if c_clean == name_clean:
                    return c

        # 4. Partial match
        for c in active:
            c_lower = c.name.lower()
            if name_lower in c_lower or c_lower in name_lower:
                return c

        return None

    def _find_account(self, accounts: List[YNABAccount], name: str) -> Optional[YNABAccount]:
        """Find account by name with fuzzy matching (exact → case-insensitive → clean → partial)."""
        name = name.strip()
        active = [a for a in accounts if not a.deleted and not a.closed]

        # 1. Exact match
        for a in active:
            if a.name == name:
                return a

        # 2. Case-insensitive
        name_lower = name.lower()
        for a in active:
            if a.name.lower() == name_lower:
                return a

        # 3. Match without special chars/emojis (Clean Match)
        name_clean = _SPECIAL_CHARS_PATTERN.sub('', name).strip().lower()
        if name_clean:
            for a in active:
                a_clean = _SPECIAL_CHARS_PATTERN.sub('', a.name).strip().lower()
                if a_clean == name_clean:
                    return a

        # 4. Partial match
        for a in active:
            a_lower = a.name.lower()
            if name_lower in a_lower or a_lower in name_lower:
                return a

        return None
