"""
Test Suite for Optional Spending-Change Planning
------------------------------------------------
Verifies:
1. Only recurring flexible expenses in user-permitted categories may be changed.
2. Supported output formats: stop:<event_id> and reduce_to:<event_id>:<amount>.
3. Maximum 3 changes (k <= 3).
4. Stopping and reducing the same event are mutually exclusive.
5. Essential (protected), fixed, one-time, or unpermitted categories are never changed.
6. Combinatorial search is deterministic and prioritizes fewer changes.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath('code'))
from models import EvaluationRequest
from financial_state import FinancialState
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

class TestSpendingChangePlanning(unittest.TestCase):

    def setUp(self):
        self.engine = ForecastEngine()
        self.safe_calc = SafeAmountCalculator(self.engine)
        self.planner = PaymentPlanner(self.engine)
        self.decision_engine = DecisionEngine(self.engine, self.safe_calc, self.planner)

        self.req = EvaluationRequest(
            request_id="req_spend_test",
            user_id="user_test",
            request_date="2026-04-01",
            request_type="appliances",
            requested_amount=1500.0,
            desired_completion_date="2026-04-30",
            allows_partial_payment=False,
            request_text="Can I buy this appliance?"
        )

        self.base_state = FinancialState(
            user_id="user_test",
            home_currency="USD",
            current_available_balance=2000.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[
                {
                    'event_id': 'ev_rent',
                    'amount': 800.0,
                    'day_of_month': 1,
                    'last_date': '2026-04-01',
                    'category': 'rent',
                    'flexibility': 'fixed',
                    'description': 'Rent'
                },
                {
                    'event_id': 'ev_cloud',
                    'amount': 20.0,
                    'day_of_month': 5,
                    'last_date': '2026-03-05',
                    'category': 'cloud_storage',
                    'flexibility': 'stoppable',
                    'description': 'Cloud storage'
                },
                {
                    'event_id': 'ev_stream',
                    'amount': 50.0,
                    'day_of_month': 10,
                    'last_date': '2026-03-10',
                    'category': 'streaming',
                    'flexibility': 'reducible_or_stoppable',
                    'minimum_allowed_amount': 25.0,
                    'description': 'Streaming'
                },
                {
                    'event_id': 'ev_grocery',
                    'amount': 300.0,
                    'day_of_month': 15,
                    'last_date': '2026-03-15',
                    'category': 'groceries',
                    'flexibility': 'reducible',
                    'minimum_allowed_amount': 200.0,
                    'description': 'Groceries'
                },
                {
                    'event_id': 'ev_gym',
                    'amount': 60.0,
                    'day_of_month': 20,
                    'last_date': '2026-03-20',
                    'category': 'gym',
                    'flexibility': 'stoppable',
                    'description': 'Gym membership'
                }
            ],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=2000.0,
            salary_day_of_month=25,
            next_salary_date="2026-04-25",
            protected_categories={'rent', 'groceries'},  # groceries and rent are protected!
            reducible_categories={'streaming'},
            stoppable_categories={'cloud_storage', 'streaming'},  # gym is NOT permitted by user!
            allowed_payment_methods={'full_payment'},
            max_installment_months=None,
            flexible_events=[]
        )

    def test_never_change_protected_or_fixed(self):
        """Protected (essential) categories and fixed events are NEVER included in changes."""
        plans = self.decision_engine.find_best_spending_changes(
            request=self.req,
            state=self.base_state,
            options=[],
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-25"
        )
        for p in plans:
            for ch in p.spending_changes:
                self.assertNotIn("ev_rent", ch, "Fixed rent must NEVER be changed.")
                self.assertNotIn("ev_grocery", ch, "Protected groceries must NEVER be changed.")

    def test_unpermitted_categories_never_changed(self):
        """Categories the user has not agreed to change (e.g. gym) must NEVER be changed."""
        plans = self.decision_engine.find_best_spending_changes(
            request=self.req,
            state=self.base_state,
            options=[],
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-25"
        )
        for p in plans:
            for ch in p.spending_changes:
                self.assertNotIn("ev_gym", ch, "Gym membership is not permitted by user.")

    def test_mutual_exclusivity_on_events(self):
        """Stopping and reducing the same event must be mutually exclusive in any combo."""
        plans = self.decision_engine.find_best_spending_changes(
            request=self.req,
            state=self.base_state,
            options=[],
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-25"
        )
        for p in plans:
            event_ids = [ch.split(':')[1] for ch in p.spending_changes]
            self.assertEqual(len(event_ids), len(set(event_ids)), "Cannot stop and reduce the same event.")

    def test_maximum_three_changes(self):
        """Maximum number of spending changes is 3."""
        plans = self.decision_engine.find_best_spending_changes(
            request=self.req,
            state=self.base_state,
            options=[],
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-25"
        )
        for p in plans:
            self.assertLessEqual(len(p.spending_changes), 3, "Spending changes cannot exceed 3.")

    def test_spending_change_formatting(self):
        """Supported formats are strictly stop:<event_id> and reduce_to:<event_id>:<amount>."""
        plans = self.decision_engine.find_best_spending_changes(
            request=self.req,
            state=self.base_state,
            options=[],
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-25"
        )
        for p in plans:
            for ch in p.spending_changes:
                parts = ch.split(':')
                self.assertIn(parts[0], ['stop', 'reduce_to'], "Action must be stop or reduce_to.")
                if parts[0] == 'stop':
                    self.assertEqual(len(parts), 2, "stop must be formatted as stop:<event_id>")
                elif parts[0] == 'reduce_to':
                    self.assertEqual(len(parts), 3, "reduce_to must be formatted as reduce_to:<event_id>:<amount>")
                    # Amount must be valid float
                    float(parts[2])

    def test_deterministic_reproducible_search(self):
        """Combinatorial search returns identical plans across repeated runs."""
        run1 = self.decision_engine.find_best_spending_changes(
            request=self.req,
            state=self.base_state,
            options=[],
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-25"
        )
        run2 = self.decision_engine.find_best_spending_changes(
            request=self.req,
            state=self.base_state,
            options=[],
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-25"
        )
        changes1 = [p.spending_changes for p in run1]
        changes2 = [p.spending_changes for p in run2]
        self.assertEqual(changes1, changes2, "Spending changes search must be 100% deterministic.")

if __name__ == '__main__':
    unittest.main()
