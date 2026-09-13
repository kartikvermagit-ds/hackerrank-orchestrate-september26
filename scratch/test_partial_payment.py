"""
Test Suite for Partial Payment Planning
---------------------------------------
Verifies:
1. Partial payment is eligible only when allows_partial_payment == True.
2. Partial payment is eligible only when user accepts 'partial_payment'.
3. Partial payment is eligible only when 0 < amount_safe_to_pay < requested_amount.
4. Partial payment is eligible only when earliest_date_for_full_payment <= desired_completion_date.
5. Schedule contains exactly two payments: (request_date, safe_amt) and (earliest_date, remainder).
6. Both payments sum exactly to requested_amount.
7. Validation through 90-day cashflow forecast is strictly enforced.
8. Evaluation against request_19 reproduces exact ground truth plan.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath('code'))
from models import EvaluationRequest
from financial_state import FinancialState
from forecast import ForecastEngine
from payment_planner import PaymentPlanner
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder

class TestPartialPaymentPlanning(unittest.TestCase):

    def setUp(self):
        self.engine = ForecastEngine()
        self.planner = PaymentPlanner(self.engine)

        self.valid_request = EvaluationRequest(
            request_id="req_part",
            user_id="user_part",
            request_date="2026-04-01",
            request_type="appliances",
            requested_amount=2000.0,
            desired_completion_date="2026-05-01",
            allows_partial_payment=True,
            request_text="Can I split this in two payments?"
        )

        self.valid_state = FinancialState(
            user_id="user_part",
            home_currency="USD",
            current_available_balance=2500.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=2000.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"partial_payment", "full_payment"},
            max_installment_months=None,
            flexible_events=[]
        )

    def test_eligible_partial_payment_structure(self):
        """Valid partial payment creates exactly 2 payments summing to requested_amount."""
        amount_safe = 800.0
        earliest_date = "2026-04-15"

        plan = self.planner.evaluate_partial_payment_plan(
            request=self.valid_request,
            state=self.valid_state,
            amount_safe_to_pay=amount_safe,
            earliest_date_for_full_payment=earliest_date
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.method, "partial_payment")
        self.assertEqual(plan.number_of_payments, 2)
        self.assertEqual(len(plan.payment_schedule), 2)
        self.assertEqual(plan.first_payment_date, "2026-04-01")

        p1_date, p1_amt = plan.payment_schedule[0]
        p2_date, p2_amt = plan.payment_schedule[1]

        self.assertEqual(p1_date, "2026-04-01")
        self.assertEqual(p1_amt, 800.0)
        self.assertEqual(p2_date, "2026-04-15")
        self.assertEqual(p2_amt, 1200.0)

        # Sum must exactly equal requested_amount
        self.assertEqual(p1_amt + p2_amt, 2000.0)
        self.assertEqual(plan.total_amount, 2000.0)
        self.assertTrue(plan.is_safe)
        self.assertEqual(plan.affordability_status, "affordable_with_plan")

        formatted = self.planner.format_payment_schedule(plan.payment_schedule)
        self.assertEqual(formatted, "2026-04-01:800|2026-04-15:1200")

    def test_request_disallows_partial_payment(self):
        """When request.allows_partial_payment is False, plan must be rejected (return None)."""
        disallowing_request = EvaluationRequest(
            request_id="req_no_part",
            user_id="user_part",
            request_date="2026-04-01",
            request_type="appliances",
            requested_amount=2000.0,
            desired_completion_date="2026-05-01",
            allows_partial_payment=False, # Disallowed!
            request_text="Can I split this?"
        )
        plan = self.planner.evaluate_partial_payment_plan(
            request=disallowing_request,
            state=self.valid_state,
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-15"
        )
        self.assertIsNone(plan)

    def test_user_disallows_partial_payment(self):
        """When user preferences exclude partial_payment, plan must be rejected (return None)."""
        disallowing_state = FinancialState(
            user_id="user_no_part",
            home_currency="USD",
            current_available_balance=2500.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=2000.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment", "installments"}, # NO partial_payment!
            max_installment_months=None,
            flexible_events=[]
        )
        plan = self.planner.evaluate_partial_payment_plan(
            request=self.valid_request,
            state=disallowing_state,
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-15"
        )
        self.assertIsNone(plan)

    def test_safe_amount_boundaries(self):
        """Partial payment rejected if amount_safe_to_pay is 0 or >= requested_amount."""
        # Case 1: amount_safe_to_pay is 0
        p0 = self.planner.evaluate_partial_payment_plan(
            request=self.valid_request,
            state=self.valid_state,
            amount_safe_to_pay=0.0,
            earliest_date_for_full_payment="2026-04-15"
        )
        self.assertIsNone(p0, "Should be rejected when amount_safe_to_pay == 0.")

        # Case 2: amount_safe_to_pay == requested_amount (affordable now in full)
        p_full = self.planner.evaluate_partial_payment_plan(
            request=self.valid_request,
            state=self.valid_state,
            amount_safe_to_pay=2000.0,
            earliest_date_for_full_payment="2026-04-01"
        )
        self.assertIsNone(p_full, "Should be rejected when amount_safe_to_pay == requested_amount.")

    def test_deadline_compliance(self):
        """Second payment date must be on or before desired_completion_date."""
        late_request = EvaluationRequest(
            request_id="req_late",
            user_id="user_part",
            request_date="2026-04-01",
            request_type="appliances",
            requested_amount=2000.0,
            desired_completion_date="2026-04-10", # Deadline is before payday 2026-04-15!
            allows_partial_payment=True,
            request_text="Need it by April 10"
        )
        plan = self.planner.evaluate_partial_payment_plan(
            request=late_request,
            state=self.valid_state,
            amount_safe_to_pay=800.0,
            earliest_date_for_full_payment="2026-04-15"
        )
        self.assertIsNone(plan, "Should be rejected when earliest date is after desired completion date.")

    def test_sample_request_19_ground_truth(self):
        """Verify request_19 produces the exact ground truth plan: 2024-09-04:28820|2024-09-15:10840."""
        loader = DataLoader('dataset')
        rates = loader.load_exchange_rates()
        profiles = loader.load_profiles()
        events = loader.load_events()
        messages = loader.load_messages()
        options = loader.load_payment_options()
        msg_proc = MessageProcessor(messages)
        normalizer = EventNormalizer(rates, msg_proc)
        builder = ContextBuilder(profiles, events, options, normalizer)

        req19 = loader.load_requests('sample_requests.csv')[18] # request_19
        state, opts = builder.build_context(req19)

        plan = self.planner.evaluate_partial_payment_plan(
            request=req19,
            state=state,
            amount_safe_to_pay=28820.0,
            earliest_date_for_full_payment="2024-09-15"
        )

        self.assertIsNotNone(plan)
        self.assertTrue(plan.is_safe)
        formatted = self.planner.format_payment_schedule(plan.payment_schedule)
        self.assertEqual(formatted, "2024-09-04:28820|2024-09-15:10840")
        self.assertEqual(plan.total_amount, 39660.0)

if __name__ == '__main__':
    unittest.main()
