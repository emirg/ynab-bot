"""Tests for domain models: Expense, ExpenseResult, UserConfiguration, YNAB models, BudgetQuery."""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from domain.models.expense import Expense, ExpenseResult, _UUID_PATTERN
from domain.models.budget_query import BudgetQueryResult, MessageResult
from domain.models.user import (
    UserConfiguration, UserStatus,
    YNABBudget, YNABAccount, YNABCategory, YNABPayee,
)
from domain.models.onboarding import OnboardingStep
from domain.time_utils import DEFAULT_TIMEZONE


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------

class TestExpense:

    def test_is_valid_basic(self, sample_expense):
        assert sample_expense.is_valid()

    def test_is_valid_minimal(self, minimal_expense):
        assert minimal_expense.is_valid()

    def test_invalid_zero_amount(self):
        e = Expense(amount=Decimal('0'), payee='Test', memo='x')
        assert not e.is_valid()

    def test_invalid_negative_amount(self):
        e = Expense(amount=Decimal('-100'), payee='Test', memo='x')
        assert not e.is_valid()

    def test_invalid_empty_payee(self):
        e = Expense(amount=Decimal('1000'), payee='', memo='x')
        assert not e.is_valid()

    def test_invalid_whitespace_payee(self):
        e = Expense(amount=Decimal('1000'), payee='   ', memo='x')
        assert not e.is_valid()

    def test_invalid_negative_confidence(self):
        e = Expense(amount=Decimal('1000'), payee='Test', memo='x', confidence=-0.1)
        assert not e.is_valid()

    def test_to_ynab_format_with_valid_category(self, sample_expense):
        result = sample_expense.to_ynab_format('budget-1', 'default-acc')
        txn = result['transaction']
        assert txn['amount'] == -25000000  # 25000 * -1000
        assert txn['payee_name'] == "McDonald's"
        assert txn['account_id'] == '660e8400-e29b-41d4-a716-446655440000'
        assert txn['category_id'] == '550e8400-e29b-41d4-a716-446655440000'
        assert txn['date'] == '2026-03-09'
        assert txn['cleared'] == 'uncleared'

    def test_to_ynab_format_uses_default_account(self, minimal_expense):
        result = minimal_expense.to_ynab_format('budget-1', 'default-acc')
        assert result['transaction']['account_id'] == 'default-acc'

    def test_to_ynab_format_invalid_uuid_omits_category(self):
        e = Expense(
            amount=Decimal('5000'), payee='Test', memo='x',
            category_id='not-a-uuid',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'category_id' not in result['transaction']

    def test_to_ynab_format_empty_category(self):
        e = Expense(amount=Decimal('5000'), payee='Test', memo='x', category_id='')
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'category_id' not in result['transaction']

    def test_to_ynab_format_whitespace_category(self):
        e = Expense(amount=Decimal('5000'), payee='Test', memo='x', category_id='   ')
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'category_id' not in result['transaction']

    def test_to_ynab_format_with_valid_payee_id(self):
        e = Expense(
            amount=Decimal('5000'), payee='Carulla', memo='x',
            payee_id='550e8400-e29b-41d4-a716-446655440000',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert result['transaction']['payee_id'] == '550e8400-e29b-41d4-a716-446655440000'

    def test_to_ynab_format_without_payee_id(self):
        e = Expense(amount=Decimal('5000'), payee='Carulla', memo='x')
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'payee_id' not in result['transaction']

    def test_to_ynab_format_invalid_uuid_payee_id_omitted(self):
        e = Expense(
            amount=Decimal('5000'), payee='Carulla', memo='x',
            payee_id='not-a-valid-uuid',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        assert 'payee_id' not in result['transaction']

    def test_payee_id_defaults_to_none(self):
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert e.payee_id is None

    def test_default_date_is_none(self):
        """Date defaults to None — callers set it with user timezone."""
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert e.date is None

    def test_default_confidence_is_zero(self):
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert e.confidence == 0.0

    def test_default_parser_source(self):
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert e.parser_source == 'unknown'

    def test_category_explanation_field(self):
        e = Expense(amount=Decimal('1'), payee='T', memo='m')
        assert e.category_explanation is None
        e.category_explanation = "sugerido por IA"
        assert e.category_explanation == "sugerido por IA"

    def test_split_defaults(self):
        e = Expense(amount=Decimal('1000'), payee='T', memo='m')
        assert e.is_split is False
        assert e.split_person is None
        assert e.split_proportion == Decimal('0.5')
        assert e.split_category_id is None
        assert e.split_category_name is None

    def test_to_ynab_format_split_50_50(self):
        e = Expense(
            amount=Decimal('50000'), payee='McDonalds', memo='almuerzo',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='660e8400-e29b-41d4-a716-446655440000',
            split_proportion=Decimal('0.5'),
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert 'category_id' not in txn
        subs = txn['subtransactions']
        assert len(subs) == 2
        assert subs[0]['amount'] == -25000000
        assert subs[0]['category_id'] == '550e8400-e29b-41d4-a716-446655440000'
        assert subs[1]['amount'] == -25000000
        assert subs[1]['category_id'] == '660e8400-e29b-41d4-a716-446655440000'
        assert subs[0]['amount'] + subs[1]['amount'] == txn['amount']

    def test_to_ynab_format_split_odd_amount(self):
        e = Expense(
            amount=Decimal('50001'), payee='Test', memo='m',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='660e8400-e29b-41d4-a716-446655440000',
            split_proportion=Decimal('0.5'),
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        subs = txn['subtransactions']
        # Sum of subtransactions must equal total
        assert subs[0]['amount'] + subs[1]['amount'] == txn['amount']
        # User share: int(50001 * 0.5 * -1000) = -25000500
        assert subs[0]['amount'] == -25000500
        # Remainder: -50001000 - (-25000500) = -25000500
        assert subs[1]['amount'] == -25000500

    def test_to_ynab_format_split_custom_proportion(self):
        e = Expense(
            amount=Decimal('90000'), payee='Test', memo='m',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='660e8400-e29b-41d4-a716-446655440000',
            split_proportion=Decimal('1') / Decimal('3'),
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        subs = txn['subtransactions']
        assert subs[0]['amount'] + subs[1]['amount'] == txn['amount']

    def test_to_ynab_format_split_no_top_level_category(self):
        e = Expense(
            amount=Decimal('10000'), payee='T', memo='m',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='660e8400-e29b-41d4-a716-446655440000',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert 'category_id' not in txn
        assert 'subtransactions' in txn

    def test_to_ynab_format_split_missing_split_category_falls_back(self):
        e = Expense(
            amount=Decimal('10000'), payee='T', memo='m',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id=None,
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert 'subtransactions' not in txn
        assert txn['category_id'] == '550e8400-e29b-41d4-a716-446655440000'

    def test_to_ynab_format_split_invalid_split_category_falls_back(self):
        e = Expense(
            amount=Decimal('10000'), payee='T', memo='m',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='not-a-uuid',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert 'subtransactions' not in txn
        assert txn['category_id'] == '550e8400-e29b-41d4-a716-446655440000'

    def test_expense_default_date_is_none(self):
        e = Expense(amount=Decimal('1000'), payee='T', memo='m')
        assert e.date is None

    def test_expense_to_ynab_format_with_none_date_uses_today(self):
        """Defensive fallback: when date is None, to_ynab_format uses user_now()."""
        e = Expense(amount=Decimal('1000'), payee='T', memo='m')
        result = e.to_ynab_format('budget-1', 'acc-1')
        # Should not raise and should have a valid date string
        assert 'date' in result['transaction']
        assert len(result['transaction']['date']) == 10  # YYYY-MM-DD

    def test_default_payer_is_user(self):
        e = Expense(amount=Decimal('1000'), payee='T', memo='m')
        assert e.payer == 'user'

    def test_to_ynab_format_other_paid_zero_sum(self):
        """Other-paid: transaction amount is 0, subtransactions cancel each other out."""
        e = Expense(
            amount=Decimal('50000'), payee='Carulla', memo='mercado con Frank',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='660e8400-e29b-41d4-a716-446655440000',
            split_proportion=Decimal('0.5'),
            payer='other',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert txn['amount'] == 0
        subs = txn['subtransactions']
        assert len(subs) == 2
        # User's share: outflow (negative)
        assert subs[0]['amount'] == -25000000
        assert subs[0]['category_id'] == '550e8400-e29b-41d4-a716-446655440000'
        # Split person's inflow (positive, cancels user's share)
        assert subs[1]['amount'] == 25000000
        assert subs[1]['category_id'] == '660e8400-e29b-41d4-a716-446655440000'
        # Subtransactions sum to 0
        assert subs[0]['amount'] + subs[1]['amount'] == 0

    def test_to_ynab_format_other_paid_no_category_id(self):
        """Other-paid with no category_id omits category_id from first subtransaction."""
        e = Expense(
            amount=Decimal('60000'), payee='Test', memo='test',
            is_split=True,
            split_category_id='660e8400-e29b-41d4-a716-446655440000',
            split_proportion=Decimal('0.5'),
            payer='other',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert txn['amount'] == 0
        subs = txn['subtransactions']
        assert 'category_id' not in subs[0]
        assert subs[1]['category_id'] == '660e8400-e29b-41d4-a716-446655440000'

    def test_to_ynab_format_other_paid_custom_proportion(self):
        """Other-paid with 1/3 proportion: user owes 1/3, inflow is 1/3."""
        e = Expense(
            amount=Decimal('90000'), payee='Test', memo='test',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='660e8400-e29b-41d4-a716-446655440000',
            split_proportion=Decimal('1') / Decimal('3'),
            payer='other',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert txn['amount'] == 0
        subs = txn['subtransactions']
        # user_share = int(90000 * (1/3) * -1000) = -30000000
        assert subs[0]['amount'] == -30000000
        assert subs[1]['amount'] == 30000000
        assert subs[0]['amount'] + subs[1]['amount'] == 0

    def test_to_ynab_format_other_paid_invalid_split_category_falls_back(self):
        """Other-paid but split_category_id is invalid UUID: should fall through to normal non-split path."""
        e = Expense(
            amount=Decimal('10000'), payee='T', memo='m',
            category_id='550e8400-e29b-41d4-a716-446655440000',
            is_split=True,
            split_category_id='not-a-uuid',
            payer='other',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        # Falls through to normal (non-split) path, amount is full expense
        assert txn['amount'] == -10000000
        assert 'subtransactions' not in txn


class TestSplitFixedAmount:
    """Tests for Expense.split_fixed_amount field and its use in to_ynab_format()."""

    SPLIT_CAT_ID = '660e8400-e29b-41d4-a716-446655440000'
    REAL_CAT_ID = '550e8400-e29b-41d4-a716-446655440000'

    def test_split_fixed_amount_default_is_none(self):
        e = Expense(amount=Decimal('1000'), payee='T', memo='m')
        assert e.split_fixed_amount is None

    def test_user_paid_split_fixed_amount_user_share_and_split_share(self):
        """User paid 60000 total; other person's fixed share is 36700.
        Splitwise gets 36700, user gets (60000 - 36700) = 23300."""
        e = Expense(
            amount=Decimal('60000'), payee='Restaurante', memo='con Frank',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_fixed_amount=Decimal('36700'),
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        subs = result['transaction']['subtransactions']
        assert len(subs) == 2
        # user_share subtransaction: -(60000 - 36700) * 1000 = -23300000
        assert subs[0]['amount'] == -23300000
        assert subs[0]['category_id'] == self.REAL_CAT_ID
        # split_share subtransaction: -36700 * 1000 = -36700000
        assert subs[1]['amount'] == -36700000
        assert subs[1]['category_id'] == self.SPLIT_CAT_ID
        # Both subtransactions must sum to total amount in milliunits
        assert subs[0]['amount'] + subs[1]['amount'] == -60000000

    def test_other_paid_split_fixed_amount_user_debt(self):
        """Other person paid 60000; other person's fixed share is 30000 (of 60000 total).
        User's debt = total - 30000 = 30000. Splitwise inflow = 30000."""
        e = Expense(
            amount=Decimal('60000'), payee='Frank', memo='Frank pagó',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_fixed_amount=Decimal('30000'),
            payer='other',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert txn['amount'] == 0
        subs = txn['subtransactions']
        assert len(subs) == 2
        # others_share_milliunits = int(30000 * -1000) = -30000000
        # user_debt_milliunits = int(60000 * -1000) - (-30000000) = -60000000 + 30000000 = -30000000
        assert subs[0]['amount'] == -30000000
        assert subs[0]['category_id'] == self.REAL_CAT_ID
        # Splitwise inflow cancels user debt
        assert subs[1]['amount'] == 30000000
        assert subs[1]['category_id'] == self.SPLIT_CAT_ID
        assert subs[0]['amount'] + subs[1]['amount'] == 0

    def test_proportion_based_path_unchanged_when_split_fixed_amount_none(self):
        """When split_fixed_amount is None, proportion-based logic is used (backward compat)."""
        e = Expense(
            amount=Decimal('60000'), payee='Test', memo='test',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_proportion=Decimal('0.5'),
            split_fixed_amount=None,
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        subs = result['transaction']['subtransactions']
        # 50/50 proportion: user_share = int(60000 * 0.5 * -1000) = -30000000
        assert subs[0]['amount'] == -30000000
        assert subs[1]['amount'] == -30000000

    # Edge case: split_fixed_amount=0 is rejected by the service layer (parser and
    # _apply_split_fields validate split_amount > 0), but we test domain behavior
    # directly here to document the boundary condition at the model level.
    def test_user_paid_split_fixed_amount_zero_nothing_to_splitwise(self):
        """Edge case: split_fixed_amount=0 means user pays everything (nothing goes to Splitwise)."""
        e = Expense(
            amount=Decimal('60000'), payee='Test', memo='test',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_fixed_amount=Decimal('0'),
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        subs = result['transaction']['subtransactions']
        assert len(subs) == 2
        # split_share = int(0 * -1000) = 0 (nothing to Splitwise)
        assert subs[1]['amount'] == 0
        # user_share = -60000000 - 0 = -60000000
        assert subs[0]['amount'] == -60000000


class TestNormalizedSplitShares:
    """Tests for normalized user/other share amounts in Expense.to_ynab_format()."""

    SPLIT_CAT_ID = '660e8400-e29b-41d4-a716-446655440000'
    REAL_CAT_ID = '550e8400-e29b-41d4-a716-446655440000'

    def test_user_paid_normalized_shares_create_split_subtransactions(self):
        e = Expense(
            amount=Decimal('200000'), payee='Carulla', memo='con Frank',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_user_share_amount=Decimal('100000'),
            split_other_share_amount=Decimal('100000'),
        )

        txn = e.to_ynab_format('budget-1', 'rappi-card')['transaction']

        assert txn['account_id'] == 'rappi-card'
        assert txn['amount'] == -200000000
        assert 'category_id' not in txn
        assert txn['subtransactions'] == [
            {'amount': -100000000, 'category_id': self.REAL_CAT_ID},
            {'amount': -100000000, 'category_id': self.SPLIT_CAT_ID},
        ]

    def test_user_paid_zero_user_share_creates_regular_splitwise_transaction(self):
        e = Expense(
            amount=Decimal('100000'), payee='Randy', memo='por Frank',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_user_share_amount=Decimal('0'),
            split_other_share_amount=Decimal('100000'),
        )

        txn = e.to_ynab_format('budget-1', 'rappi-card')['transaction']

        assert txn['account_id'] == 'rappi-card'
        assert txn['amount'] == -100000000
        assert txn['category_id'] == self.SPLIT_CAT_ID
        assert 'subtransactions' not in txn

    def test_user_paid_zero_other_share_creates_regular_real_category_transaction(self):
        e = Expense(
            amount=Decimal('200000'), payee='Carulla', memo='todo es mio',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_user_share_amount=Decimal('200000'),
            split_other_share_amount=Decimal('0'),
        )

        txn = e.to_ynab_format('budget-1', 'rappi-card')['transaction']

        assert txn['account_id'] == 'rappi-card'
        assert txn['amount'] == -200000000
        assert txn['category_id'] == self.REAL_CAT_ID
        assert 'subtransactions' not in txn

    def test_other_paid_normalized_user_share_creates_zero_sum_transaction(self):
        e = Expense(
            amount=Decimal('200000'), payee='Frank', memo='por mi en Carulla',
            category_id=self.REAL_CAT_ID,
            account_id='shared-transactions',
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_user_share_amount=Decimal('200000'),
            split_other_share_amount=Decimal('0'),
            payer='other',
        )

        txn = e.to_ynab_format('budget-1', 'fallback-account')['transaction']

        assert txn['account_id'] == 'shared-transactions'
        assert txn['amount'] == 0
        assert txn['subtransactions'] == [
            {'amount': -200000000, 'category_id': self.REAL_CAT_ID},
            {'amount': 200000000, 'category_id': self.SPLIT_CAT_ID},
        ]

    def test_other_paid_me_compro_full_user_share_zero_sum_shape(self):
        e = Expense(
            amount=Decimal('14200'), payee='Farmatodo', memo='Frank me compro agua oxigenada',
            category_id=self.REAL_CAT_ID,
            account_id='shared-transactions',
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_user_share_amount=Decimal('14200'),
            split_other_share_amount=Decimal('0'),
            payer='other',
        )

        txn = e.to_ynab_format('budget-1', 'fallback-account')['transaction']

        assert txn['account_id'] == 'shared-transactions'
        assert txn['amount'] == 0
        assert txn['subtransactions'] == [
            {'amount': -14200000, 'category_id': self.REAL_CAT_ID},
            {'amount': 14200000, 'category_id': self.SPLIT_CAT_ID},
        ]

    def test_other_person_gasto_without_conmigo_half_share_zero_sum_shape(self):
        e = Expense(
            amount=Decimal('71800'), payee='Pret', memo='Frank gasto en Pret',
            category_id=self.REAL_CAT_ID,
            account_id='shared-transactions',
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_user_share_amount=Decimal('35900'),
            split_other_share_amount=Decimal('35900'),
            payer='other',
        )

        txn = e.to_ynab_format('budget-1', 'fallback-account')['transaction']

        assert txn['account_id'] == 'shared-transactions'
        assert txn['amount'] == 0
        assert txn['subtransactions'] == [
            {'amount': -35900000, 'category_id': self.REAL_CAT_ID},
            {'amount': 35900000, 'category_id': self.SPLIT_CAT_ID},
        ]


class TestZeroProportionFullDebt:
    """Tests for split_proportion=0 (user paid 100% for someone else, like a loan)."""

    SPLIT_CAT_ID = '660e8400-e29b-41d4-a716-446655440000'
    REAL_CAT_ID = '550e8400-e29b-41d4-a716-446655440000'

    def test_user_paid_zero_proportion_all_goes_to_splitwise(self):
        """User paid 100k but proportion=0 means it's entirely for the other person.
        user_share=0, split_share=full amount."""
        e = Expense(
            amount=Decimal('100000'), payee='Carulla', memo='por Frank',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_proportion=Decimal('0'),
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        subs = result['transaction']['subtransactions']
        assert len(subs) == 2
        assert subs[0]['amount'] == 0  # user keeps nothing
        assert subs[1]['amount'] == -100000000  # all to splitwise
        assert subs[0]['amount'] + subs[1]['amount'] == -100000000

    def test_other_paid_zero_proportion_user_owes_nothing(self):
        """Other person paid and proportion=0 means user owes nothing (other paid for themselves)."""
        e = Expense(
            amount=Decimal('50000'), payee='Restaurante', memo='Frank pagó',
            category_id=self.REAL_CAT_ID,
            is_split=True,
            split_category_id=self.SPLIT_CAT_ID,
            split_proportion=Decimal('0'),
            payer='other',
        )
        result = e.to_ynab_format('budget-1', 'acc-1')
        txn = result['transaction']
        assert txn['amount'] == 0
        subs = txn['subtransactions']
        assert subs[0]['amount'] == 0  # user owes nothing
        assert subs[1]['amount'] == 0  # no splitwise inflow


class TestUUIDPattern:

    @pytest.mark.parametrize('uuid', [
        '550e8400-e29b-41d4-a716-446655440000',
        'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE',
        '00000000-0000-0000-0000-000000000000',
    ])
    def test_valid_uuids(self, uuid):
        assert _UUID_PATTERN.match(uuid)

    @pytest.mark.parametrize('invalid', [
        'not-a-uuid',
        '550e8400e29b41d4a716446655440000',
        '550e8400-e29b-41d4-a716',
        '',
        'Groceries',
    ])
    def test_invalid_uuids(self, invalid):
        assert not _UUID_PATTERN.match(invalid)


class TestExpenseResult:

    def test_success_result(self, sample_expense):
        result = ExpenseResult.success_result(sample_expense, 'txn-1')
        assert result.success is True
        assert result.expense == sample_expense
        assert result.transaction_id == 'txn-1'
        assert result.error_message is None

    def test_error_result(self):
        result = ExpenseResult.error_result('Something failed')
        assert result.success is False
        assert result.error_message == 'Something failed'
        assert result.expense is None


# ---------------------------------------------------------------------------
# UserConfiguration
# ---------------------------------------------------------------------------

class TestUserConfiguration:

    def test_is_configured_requires_both(self, authorized_user):
        assert authorized_user.is_configured()

    def test_not_configured_missing_budget(self):
        u = UserConfiguration(telegram_id=1, default_account_id='acc-1')
        assert not u.is_configured()

    def test_not_configured_missing_account(self):
        u = UserConfiguration(telegram_id=1, budget_id='budget-1')
        assert not u.is_configured()

    def test_status_checks(self, authorized_user, pending_user, blocked_user):
        assert authorized_user.is_authorized()
        assert not authorized_user.is_pending()
        assert not authorized_user.is_blocked()

        assert pending_user.is_pending()
        assert not pending_user.is_authorized()

        assert blocked_user.is_blocked()
        assert not blocked_user.is_authorized()

    def test_authorize(self, pending_user):
        pending_user.authorize(approved_by=999)
        assert pending_user.is_authorized()
        assert pending_user.approved_by == 999
        assert pending_user.approved_at is not None

    def test_block(self, authorized_user):
        authorized_user.block()
        assert authorized_user.is_blocked()

    def test_update_budget(self, authorized_user):
        old_updated = authorized_user.updated_at
        authorized_user.update_budget('new-budget')
        assert authorized_user.budget_id == 'new-budget'

    def test_update_default_account(self, authorized_user):
        authorized_user.update_default_account('new-acc', 'New Account')
        assert authorized_user.default_account_id == 'new-acc'
        assert authorized_user.default_account_name == 'New Account'

    def test_update_profile(self, authorized_user):
        authorized_user.update_profile(username='new', first_name='New', last_name='Name')
        assert authorized_user.username == 'new'
        assert authorized_user.first_name == 'New'
        assert authorized_user.last_name == 'Name'

    def test_update_profile_partial(self, authorized_user):
        old_first = authorized_user.first_name
        authorized_user.update_profile(last_name='Changed')
        assert authorized_user.first_name == old_first
        assert authorized_user.last_name == 'Changed'

    def test_get_display_name_full(self, authorized_user):
        assert authorized_user.get_display_name() == 'Test User'

    def test_get_display_name_first_only(self):
        u = UserConfiguration(telegram_id=1, first_name='Alice')
        assert u.get_display_name() == 'Alice'

    def test_get_display_name_username(self):
        u = UserConfiguration(telegram_id=1, username='alice')
        assert u.get_display_name() == '@alice'

    def test_get_display_name_fallback(self):
        u = UserConfiguration(telegram_id=42)
        assert u.get_display_name() == 'User 42'

    def test_default_status_is_pending(self):
        u = UserConfiguration(telegram_id=1)
        assert u.status == UserStatus.PENDING

    def test_has_ynab_token_false_by_default(self):
        u = UserConfiguration(telegram_id=1)
        assert not u.has_ynab_token()

    def test_has_ynab_token_true(self):
        u = UserConfiguration(telegram_id=1, ynab_access_token='tok')
        assert u.has_ynab_token()

    def test_is_token_expired_none_expires(self):
        u = UserConfiguration(telegram_id=1, ynab_access_token='tok')
        assert u.is_token_expired()

    def test_is_token_expired_future(self):
        u = UserConfiguration(
            telegram_id=1,
            ynab_access_token='tok',
            ynab_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert not u.is_token_expired()

    def test_is_token_expired_within_buffer(self):
        u = UserConfiguration(
            telegram_id=1,
            ynab_access_token='tok',
            ynab_token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
        )
        assert u.is_token_expired()

    def test_update_ynab_tokens(self):
        u = UserConfiguration(telegram_id=1)
        u.update_ynab_tokens('access', 'refresh', 7200)
        assert u.ynab_access_token == 'access'
        assert u.ynab_refresh_token == 'refresh'
        assert u.ynab_token_expires_at is not None
        assert u.ynab_token_expires_at > datetime.now(timezone.utc)
        assert u.ynab_token_expires_at.tzinfo is not None

    def test_clear_ynab_tokens(self):
        u = UserConfiguration(telegram_id=1, ynab_access_token='tok', ynab_refresh_token='ref')
        u.clear_ynab_tokens()
        assert u.ynab_access_token is None
        assert u.ynab_refresh_token is None
        assert u.ynab_token_expires_at is None

    def test_user_configuration_default_timezone(self):
        u = UserConfiguration(telegram_id=1)
        assert u.timezone == DEFAULT_TIMEZONE

    def test_user_configuration_update_timezone(self):
        u = UserConfiguration(telegram_id=1)
        old_updated = u.updated_at
        import time; time.sleep(0.01)  # ensure updated_at changes
        u.update_timezone("America/Bogota")
        assert u.timezone == "America/Bogota"
        assert u.updated_at > old_updated

    def test_last_weekly_summary_sent_default_is_none(self):
        u = UserConfiguration(telegram_id=1)
        assert u.last_weekly_summary_sent is None

    def test_mark_weekly_summary_sent_sets_field(self):
        import time
        from datetime import timezone as tz
        u = UserConfiguration(telegram_id=1)
        before = datetime.now(tz.utc)
        time.sleep(0.01)
        u.mark_weekly_summary_sent()
        assert u.last_weekly_summary_sent is not None
        # Value is UTC-aware
        assert u.last_weekly_summary_sent.tzinfo is not None
        assert u.last_weekly_summary_sent.tzinfo == tz.utc

    def test_mark_weekly_summary_sent_updates_updated_at(self):
        import time
        u = UserConfiguration(telegram_id=1)
        old_updated = u.updated_at
        time.sleep(0.01)
        u.mark_weekly_summary_sent()
        assert u.updated_at > old_updated

    def test_confirm_before_create_default_is_false(self):
        u = UserConfiguration(telegram_id=1)
        assert u.confirm_before_create is False

    def test_toggle_confirmation_enables(self):
        import time
        u = UserConfiguration(telegram_id=1)
        old_updated = u.updated_at
        time.sleep(0.01)
        u.toggle_confirmation(True)
        assert u.confirm_before_create is True
        assert u.updated_at > old_updated

    def test_toggle_confirmation_disables(self):
        import time
        u = UserConfiguration(telegram_id=1, confirm_before_create=True)
        old_updated = u.updated_at
        time.sleep(0.01)
        u.toggle_confirmation(False)
        assert u.confirm_before_create is False
        assert u.updated_at > old_updated

    def test_toggle_confirmation_updated_at_is_datetime(self):
        import time
        u = UserConfiguration(telegram_id=1)
        old_updated = u.updated_at
        time.sleep(0.01)
        u.toggle_confirmation(True)
        assert isinstance(u.updated_at, datetime)
        assert u.updated_at > old_updated


# ---------------------------------------------------------------------------
# YNAB domain models
# ---------------------------------------------------------------------------

class TestYNABBudget:

    def test_from_api_response(self):
        data = {'id': 'b1', 'name': 'Budget', 'currency_format': {'iso_code': 'COP'}}
        budget = YNABBudget.from_api_response(data)
        assert budget.id == 'b1'
        assert budget.name == 'Budget'

    def test_from_api_response_missing_currency(self):
        data = {'id': 'b1', 'name': 'Budget'}
        budget = YNABBudget.from_api_response(data)
        assert budget.currency_format == {}


class TestYNABAccount:

    def test_from_api_response(self):
        data = {
            'id': 'a1', 'name': 'Nu', 'type': 'creditCard',
            'balance': 500000, 'cleared_balance': 400000,
            'uncleared_balance': 100000, 'closed': False, 'deleted': False,
        }
        account = YNABAccount.from_api_response(data)
        assert account.id == 'a1'
        assert account.balance == 500000
        assert not account.closed

    def test_from_api_response_defaults(self):
        data = {'id': 'a2', 'name': 'Cash', 'type': 'cash'}
        account = YNABAccount.from_api_response(data)
        assert account.balance == 0
        assert not account.closed
        assert not account.deleted


class TestYNABPayee:

    def test_from_api_response_full(self):
        data = {'id': 'p1', 'name': 'Carulla', 'deleted': False}
        payee = YNABPayee.from_api_response(data)
        assert payee.id == 'p1'
        assert payee.name == 'Carulla'
        assert payee.deleted is False

    def test_from_api_response_deleted(self):
        data = {'id': 'p2', 'name': 'Old Store', 'deleted': True}
        payee = YNABPayee.from_api_response(data)
        assert payee.deleted is True

    def test_from_api_response_deleted_defaults_to_false(self):
        data = {'id': 'p3', 'name': 'Rappi'}
        payee = YNABPayee.from_api_response(data)
        assert payee.deleted is False

    def test_from_api_response_preserves_name(self):
        data = {'id': 'p4', 'name': 'Café Juan Valdez'}
        payee = YNABPayee.from_api_response(data)
        assert payee.name == 'Café Juan Valdez'

    def test_dataclass_equality(self):
        p1 = YNABPayee(id='p1', name='Carulla', deleted=False)
        p2 = YNABPayee(id='p1', name='Carulla', deleted=False)
        assert p1 == p2

    def test_dataclass_inequality(self):
        p1 = YNABPayee(id='p1', name='Carulla')
        p2 = YNABPayee(id='p2', name='Exito')
        assert p1 != p2


class TestYNABCategory:

    def test_from_api_response(self):
        data = {
            'id': 'c1', 'name': 'Groceries', 'budgeted': 500000,
            'activity': -200000, 'balance': 300000,
        }
        cat = YNABCategory.from_api_response(data, 'Essentials')
        assert cat.id == 'c1'
        assert cat.full_name == 'Essentials \u2192 Groceries'
        assert cat.group_name == 'Essentials'

    def test_from_api_response_defaults(self):
        data = {'id': 'c2', 'name': 'Fun'}
        cat = YNABCategory.from_api_response(data, 'Optional')
        assert cat.budgeted == 0
        assert not cat.deleted
        assert not cat.hidden


# ---------------------------------------------------------------------------
# BudgetQueryResult
# ---------------------------------------------------------------------------

class TestBudgetQueryResult:

    def test_success_result(self):
        data = {'name': 'Groceries', 'balance': 300000}
        r = BudgetQueryResult.success_result('category_balance', data)
        assert r.success is True
        assert r.query_type == 'category_balance'
        assert r.data == data
        assert r.error_message is None

    def test_error_result(self):
        r = BudgetQueryResult.error_result('category_balance', 'No encontrada')
        assert r.success is False
        assert r.query_type == 'category_balance'
        assert r.error_message == 'No encontrada'
        assert r.data is None

    def test_default_values(self):
        r = BudgetQueryResult(success=True, query_type='budget_summary')
        assert r.data is None
        assert r.error_message is None


# ---------------------------------------------------------------------------
# MessageResult
# ---------------------------------------------------------------------------

class TestMessageResult:

    def test_expense_intent(self, sample_expense):
        expense_result = ExpenseResult.success_result(sample_expense, 'txn-1')
        r = MessageResult(intent='expense', expense_result=expense_result)
        assert r.intent == 'expense'
        assert r.expense_result is expense_result
        assert r.query_result is None

    def test_query_intent(self):
        query_result = BudgetQueryResult.success_result(
            'account_balance', {'name': 'Nu Card', 'balance': 500000}
        )
        r = MessageResult(intent='query', query_result=query_result)
        assert r.intent == 'query'
        assert r.query_result is query_result
        assert r.expense_result is None

    def test_default_values(self):
        r = MessageResult(intent='expense')
        assert r.expense_result is None
        assert r.query_result is None


# ---------------------------------------------------------------------------
# OnboardingStep
# ---------------------------------------------------------------------------

class TestOnboardingStep:

    def test_enum_values(self):
        assert OnboardingStep.NEEDS_YNAB_CONNECTION.value == "needs_ynab_connection"
        assert OnboardingStep.NEEDS_BUDGET.value == "needs_budget"
        assert OnboardingStep.NEEDS_ACCOUNT.value == "needs_account"
        assert OnboardingStep.COMPLETE.value == "complete"

    def test_enum_members(self):
        assert len(OnboardingStep) == 4
        assert OnboardingStep("needs_ynab_connection") == OnboardingStep.NEEDS_YNAB_CONNECTION
