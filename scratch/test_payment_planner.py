"""
Test Suite for Payment Plan Evaluation
---------------------------------------
Verifies:
1. Evaluates supplied payment options from request_payment_options.csv.
2. Respects payment start date, recurring interval, and number of payments.
3. Respects financing fees and total payable amount.
4. Respects user payment_methods_user_will_consider.
5. Respects max_installment_months tenure constraints.
6. Simulates every eligible option through deterministic forecast.
7. Enforces that every payment is safe, minimum balance is protected, and deadline is met.
8. Ensures final schedule matches supplied option without inventing schedules.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath('code'))
from models import EvaluationRequest, PaymentOption, CandidatePlan
from financial_state import FinancialState
from forecast import ForecastEngine
from payment_planner import PaymentPlanner

class TestPaymentPlanner(unittest.TestCase):

    def setUp(self):
        self.engine = ForecastEngine()
        self.planner = PaymentPlanner(self.engine)

        self.sample_request = EvaluationRequest(
            request_id="req_test",
            user_id="user_test",
            request_date="2026-04-01",
            request_type="electronics",
            requested_amount=1500.0,
            desired_completion_date="2026-07-15",
            allows_partial_payment=True,
            request_text="Can I buy a laptop with installments?"
        )

        self.sample_state = FinancialState(
            user_id="user_test",
            home_currency="USD",
            current_available_balance=3000.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=2500.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"installments", "full_payment"},
            max_installment_months=6.0,
            flexible_events=[]
        )

        self.valid_option = PaymentOption(
            payment_option_id="opt_3m",
            request_id="req_test",
            payment_method="installments",
            payment_amount=520.0,
            number_of_payments=3,
            first_payment_date="2026-04-05",
            payment_frequency_days=30.0,
            financing_fee=60.0,
            total_payable_amount=1560.0
        )

    def test_respects_schedule_structure(self):
        """Installment schedule strictly matches option start date, interval, and payments."""
        plan = self.planner.evaluate_installment_option(
            option=self.valid_option,
            request=self.sample_request,
            state=self.sample_state
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.number_of_payments, 3)
        self.assertEqual(plan.total_amount, 1560.0)
        self.assertEqual(plan.payment_option_id, "opt_3m")
        
        # Check generated dates: 2026-04-05, 2026-05-05, 2026-06-04
        dates = [d for d, amt in plan.payment_schedule]
        amounts = [amt for d, amt in plan.payment_schedule]
        self.assertEqual(dates, ["2026-04-05", "2026-05-05", "2026-06-04"])
        self.assertEqual(amounts, [520.0, 520.0, 520.0])

        formatted = self.planner.format_payment_schedule(plan.payment_schedule)
        self.assertEqual(formatted, "2026-04-05:520|2026-05-05:520|2026-06-04:520")

    def test_respects_user_allowed_payment_methods(self):
        """If user will NOT consider installments, option must be rejected (return None)."""
        disallowed_state = FinancialState(
            user_id="user_no_inst",
            home_currency="USD",
            current_available_balance=5000.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=2500.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment"}, # NO installments allowed!
            max_installment_months=None,
            flexible_events=[]
        )
        plan = self.planner.evaluate_installment_option(
            option=self.valid_option,
            request=self.sample_request,
            state=disallowed_state
        )
        self.assertIsNone(plan, "Must return None when user does not consider installments.")

    def test_respects_max_installment_months(self):
        """If option tenure exceeds max_installment_months, option must be rejected."""
        long_option = PaymentOption(
            payment_option_id="opt_12m",
            request_id="req_test",
            payment_method="installments",
            payment_amount=140.0,
            number_of_payments=12, # 12 months > max 6.0 months
            first_payment_date="2026-04-05",
            payment_frequency_days=30.0,
            financing_fee=180.0,
            total_payable_amount=1680.0
        )
        plan = self.planner.evaluate_installment_option(
            option=long_option,
            request=self.sample_request,
            state=self.sample_state # max_installment_months = 6.0
        )
        self.assertIsNone(plan, "Must reject installment option exceeding user's max tenure.")

    def test_violating_completion_date_is_marked_unsafe(self):
        """If installment schedule finishes after desired_completion_date, it is unsafe."""
        tight_deadline_request = EvaluationRequest(
            request_id="req_tight",
            user_id="user_test",
            request_date="2026-04-01",
            request_type="electronics",
            requested_amount=1500.0,
            desired_completion_date="2026-05-01", # Deadline is before payment 2 (2026-05-05)
            allows_partial_payment=False,
            request_text="Need it done by May 1"
        )
        plan = self.planner.evaluate_installment_option(
            option=self.valid_option,
            request=tight_deadline_request,
            state=self.sample_state
        )
        self.assertIsNotNone(plan)
        self.assertFalse(plan.is_safe, "Plan finishing after deadline must have is_safe=False.")
        self.assertEqual(plan.affordability_status, 'not_affordable')

    def test_violating_minimum_balance_is_marked_unsafe(self):
        """If paying installment violates minimum_balance_to_keep, it is unsafe."""
        low_balance_state = FinancialState(
            user_id="user_poor",
            home_currency="USD",
            current_available_balance=1200.0,
            minimum_balance_to_keep=1000.0, # Headroom is only 200.0
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=0.0, # No salary
            salary_day_of_month=None,
            next_salary_date=None,
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"installments"},
            max_installment_months=6.0,
            flexible_events=[]
        )
        # Payment 1 is 520.0, but headroom is 200 -> 1200 - 520 = 680 < 1000 min bal
        plan = self.planner.evaluate_installment_option(
            option=self.valid_option,
            request=self.sample_request,
            state=low_balance_state
        )
        self.assertIsNotNone(plan)
        self.assertFalse(plan.is_safe, "Plan dipping below minimum balance must have is_safe=False.")
        self.assertEqual(plan.affordability_status, 'not_affordable')

    def test_safe_installment_plan_is_affordable_with_plan(self):
        """A valid plan with sufficient cash and meeting deadline is marked safe and affordable_with_plan."""
        plan = self.planner.evaluate_installment_option(
            option=self.valid_option,
            request=self.sample_request,
            state=self.sample_state
        )
        self.assertIsNotNone(plan)
        self.assertTrue(plan.is_safe)
        self.assertEqual(plan.affordability_status, 'affordable_with_plan')

if __name__ == '__main__':
    unittest.main()
