"""
Test Suite for earliest_date_for_full_payment
----------------------------------------------
Verifies:
1. When full amount is safe today, earliest_date equals request_date.
2. Independent of user's payment-method preference (financial capacity vs method preference).
3. Evaluated strictly without optional spending changes.
4. Returns None (null internally) when full payment is not safe within the 90-day forecast.
5. Users with no confirmed future income (gig workers) return None when not affordable now.
6. Future payday safety is accurately determined based on confirmed salary settlement dates.
7. Zero hardcoding of sample IDs or ground truth labels.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath('code'))
from models import FinancialProfile, NormalizedEvent
from financial_state import FinancialState
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator

class TestEarliestDateForFullPayment(unittest.TestCase):

    def setUp(self):
        self.engine = ForecastEngine()
        self.calc = SafeAmountCalculator(self.engine)

    def test_affordable_now_equals_request_date(self):
        """When user has sufficient headroom on request_date, earliest_date MUST equal request_date."""
        state = FinancialState(
            user_id="test_user_01",
            home_currency="USD",
            current_available_balance=10000.0,
            minimum_balance_to_keep=2000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=4000.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment", "installments"},
            max_installment_months=6,
            flexible_events=[]
        )
        request_date = "2026-04-01"
        requested_amount = 3000.0

        earliest = self.calc.compute_earliest_date_for_full_payment(
            state=state,
            request_date=request_date,
            requested_amount=requested_amount
        )
        self.assertEqual(earliest, request_date, "Should equal request_date when affordable now.")

    def test_independent_of_payment_method_preference(self):
        """
        Even if user specifies they will ONLY consider installments (no full_payment),
        earliest_date_for_full_payment reflects financial capacity and MUST equal request_date
        if safe today.
        """
        state = FinancialState(
            user_id="test_user_pref",
            home_currency="USD",
            current_available_balance=10000.0,
            minimum_balance_to_keep=2000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=5.0,
            salary_amount=4000.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"installments"},  # NO full_payment allowed by user preference!
            max_installment_months=3,
            flexible_events=[]
        )
        request_date = "2026-04-01"
        requested_amount = 2000.0

        earliest = self.calc.compute_earliest_date_for_full_payment(
            state=state,
            request_date=request_date,
            requested_amount=requested_amount
        )
        self.assertEqual(earliest, request_date,
                         "Financial capacity is independent of user's payment method preferences.")

    def test_without_optional_spending_changes(self):
        """
        earliest_date_for_full_payment is evaluated without spending changes.
        Even if flexible expenses exist that could be stopped, they are not stopped.
        """
        state = FinancialState(
            user_id="test_user_spend",
            home_currency="USD",
            current_available_balance=3000.0,
            minimum_balance_to_keep=2000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[
                {
                    'event_id': 'ev_sub',
                    'amount': 500.0,
                    'day_of_month': 5,
                    'last_date': '2026-03-05',
                    'category': 'entertainment',
                    'flexibility': 'stoppable',
                    'description': 'Streaming'
                }
            ],
            scheduled_debits={},
            daily_variable_burn=20.0,
            salary_amount=3000.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories={"entertainment"},
            allowed_payment_methods={"full_payment"},
            max_installment_months=None,
            flexible_events=[]
        )
        request_date = "2026-04-01"
        requested_amount = 800.0

        safe_now = self.calc.compute_safe_amount(state, request_date, requested_amount)
        self.assertLess(safe_now, requested_amount, "Should not be safe today without spending changes.")

        earliest = self.calc.compute_earliest_date_for_full_payment(
            state=state,
            request_date=request_date,
            requested_amount=requested_amount
        )
        self.assertEqual(earliest, "2026-04-15", "Should wait until confirmed payday when cash is replenished.")

    def test_gig_worker_no_salary_returns_none(self):
        """Gig workers without confirmed recurring salary cannot become safe later if not safe today."""
        state = FinancialState(
            user_id="test_gig_worker",
            home_currency="USD",
            current_available_balance=1500.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=25.0,
            salary_amount=None,
            salary_day_of_month=None,
            next_salary_date=None,
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment"},
            max_installment_months=None,
            flexible_events=[]
        )
        request_date = "2026-05-01"
        requested_amount = 1200.0

        earliest = self.calc.compute_earliest_date_for_full_payment(
            state=state,
            request_date=request_date,
            requested_amount=requested_amount
        )
        self.assertIsNone(earliest, "Gig worker with insufficient funds should return None.")

    def test_unaffordable_amount_exceeding_future_savings_returns_none(self):
        """When requested amount is so large it cannot be safely paid even across the 90-day window."""
        state = FinancialState(
            user_id="test_big_spender",
            home_currency="USD",
            current_available_balance=2000.0,
            minimum_balance_to_keep=1500.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[
                {
                    'event_id': 'ev_rent',
                    'amount': 2000.0,
                    'day_of_month': 1,
                    'last_date': '2026-04-01',
                    'category': 'rent',
                    'flexibility': 'fixed',
                    'description': 'Rent'
                }
            ],
            scheduled_debits={},
            daily_variable_burn=20.0,
            salary_amount=2500.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment"},
            max_installment_months=None,
            flexible_events=[]
        )
        request_date = "2026-04-02"
        requested_amount = 50000.0

        earliest = self.calc.compute_earliest_date_for_full_payment(
            state=state,
            request_date=request_date,
            requested_amount=requested_amount
        )
        self.assertIsNone(earliest, "Excessive purchase must return None.")


if __name__ == '__main__':
    unittest.main()
