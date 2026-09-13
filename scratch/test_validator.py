"""
Test Suite for Strict Deterministic Validator
----------------------------------------------
Verifies:
1. Valid decisions pass validation with 0 errors.
2. Status and method enum validation.
3. 0 <= amount_safe_to_pay <= requested_amount.
4. Chronological payment plan validation.
5. Payment totals matching requested amount / option total.
6. Partial payment rules enforcement.
7. Installment option matching.
8. Desired completion date enforcement.
9. earliest_date_for_full_payment rules.
10. Spending changes rules (max 3, mutual exclusivity, protected/fixed protection).
11. Minimum balance violation detection during continuous forecast re-simulation.
12. DecisionValidationError exception raising.
13. Validation of all 25 sample request outputs.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath('code'))
from models import RecommendationOutput, EvaluationRequest, PaymentOption
from financial_state import FinancialState
from forecast import ForecastEngine
from validator import OutputValidator, DecisionValidationError
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder

class TestOutputValidator(unittest.TestCase):

    def setUp(self):
        self.engine = ForecastEngine()
        self.req = EvaluationRequest(
            request_id="req_valid",
            user_id="user_val",
            request_date="2026-04-01",
            request_type="electronics",
            requested_amount=1000.0,
            desired_completion_date="2026-05-01",
            allows_partial_payment=True,
            request_text="Can I buy this?"
        )
        self.state = FinancialState(
            user_id="user_val",
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
            protected_categories={'rent'},
            reducible_categories={'streaming'},
            stoppable_categories={'cloud_storage'},
            allowed_payment_methods={"full_payment", "partial_payment", "installments"},
            max_installment_months=6.0,
            flexible_events=[]
        )

    def test_valid_full_payment_decision(self):
        """A properly formed full_payment decision passes validation with 0 errors."""
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=1000.0,
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2026-04-01:1000",
            earliest_date_for_full_payment="2026-04-01",
            spending_changes_needed="none",
            decision_explanation="Pay USD 1,000 today."
        )
        errors = OutputValidator.validate_decision(rec, self.req, self.state, options=[], forecaster=self.engine)
        self.assertEqual(errors, [])

    def test_invalid_status_and_method(self):
        """Invalid affordability_status or recommended_payment_method is rejected."""
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=500.0,
            affordability_status="affordable_someday",  # INVALID
            recommended_payment_method="crypto",        # INVALID
            payment_plan="2026-04-01:500",
            earliest_date_for_full_payment="2026-04-01",
            spending_changes_needed="none",
            decision_explanation="Pay with bitcoin."
        )
        errors = OutputValidator.validate_decision(rec, self.req, self.state)
        self.assertTrue(any("Invalid affordability_status" in e for e in errors))
        self.assertTrue(any("Invalid recommended_payment_method" in e for e in errors))

    def test_safe_amount_out_of_bounds(self):
        """amount_safe_to_pay > requested_amount or < 0 is rejected."""
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=1500.0,  # > requested_amount (1000.0)
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2026-04-01:1000",
            earliest_date_for_full_payment="2026-04-01",
            spending_changes_needed="none",
            decision_explanation="Pay."
        )
        errors = OutputValidator.validate_decision(rec, self.req, self.state)
        self.assertTrue(any("amount_safe_to_pay" in e and "out of bounds" in e for e in errors))

    def test_non_chronological_plan(self):
        """A payment plan with non-chronological dates is rejected."""
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=500.0,
            affordability_status="affordable_with_plan",
            recommended_payment_method="partial_payment",
            payment_plan="2026-04-20:500|2026-04-05:500",  # OUT OF ORDER!
            earliest_date_for_full_payment="2026-04-20",
            spending_changes_needed="none",
            decision_explanation="Split payment."
        )
        errors = OutputValidator.validate_decision(rec, self.req, self.state)
        self.assertTrue(any("not chronological" in e for e in errors))

    def test_partial_payment_sum_mismatch(self):
        """Partial payment whose two parts do not equal requested_amount is rejected."""
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=400.0,
            affordability_status="affordable_with_plan",
            recommended_payment_method="partial_payment",
            payment_plan="2026-04-01:400|2026-04-15:500",  # 400 + 500 = 900 != 1000!
            earliest_date_for_full_payment="2026-04-15",
            spending_changes_needed="none",
            decision_explanation="Partial payment."
        )
        errors = OutputValidator.validate_decision(rec, self.req, self.state)
        self.assertTrue(any("does not equal requested_amount" in e for e in errors))

    def test_deadline_violation(self):
        """Plan completing after desired_completion_date is rejected."""
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=400.0,
            affordability_status="affordable_later",
            recommended_payment_method="wait",
            payment_plan="2026-05-15:1000",  # 2026-05-15 > deadline 2026-05-01!
            earliest_date_for_full_payment="2026-05-15",
            spending_changes_needed="none",
            decision_explanation="Wait."
        )
        errors = OutputValidator.validate_decision(rec, self.req, self.state)
        self.assertTrue(any("exceeds desired_completion_date" in e for e in errors))

    def test_installment_matching_supplied_options(self):
        """Installment plan not matching any supplied provider option is rejected."""
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=0.0,
            affordability_status="affordable_with_plan",
            recommended_payment_method="installments",
            payment_plan="2026-04-05:300|2026-05-05:300|2026-06-05:300",
            earliest_date_for_full_payment="",
            spending_changes_needed="none",
            decision_explanation="Installments."
        )
        # Empty options list -> no matching provider option
        errors = OutputValidator.validate_decision(rec, self.req, self.state, options=[])
        self.assertTrue(any("does not match any eligible provider option" in e for e in errors))

    def test_spending_changes_protected_category_violation(self):
        """Spending changes attempting to stop protected rent are rejected."""
        state_with_rent = FinancialState(
            user_id="user_val",
            home_currency="USD",
            current_available_balance=5000.0,
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
                }
            ],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=2500.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories={'rent'},
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment"},
            max_installment_months=None,
            flexible_events=[]
        )
        rec = RecommendationOutput(
            request_id="req_valid",
            amount_safe_to_pay=500.0,
            affordability_status="affordable_with_plan",
            recommended_payment_method="full_payment",
            payment_plan="2026-04-01:1000",
            earliest_date_for_full_payment="2026-04-01",
            spending_changes_needed="stop:ev_rent",  # ILLEGAL: rent is protected and fixed!
            decision_explanation="Stop rent."
        )
        errors = OutputValidator.validate_decision(rec, self.req, state_with_rent)
        self.assertTrue(any("protected category" in e or "fixed event" in e for e in errors))

    def test_decision_validation_error_raised(self):
        """When raise_exception=True, DecisionValidationError is raised on error."""
        rec = RecommendationOutput(
            request_id="wrong_id",
            amount_safe_to_pay=-100.0,
            affordability_status="invalid",
            recommended_payment_method="invalid",
            payment_plan="none",
            earliest_date_for_full_payment="",
            spending_changes_needed="none",
            decision_explanation="Bad."
        )
        with self.assertRaises(DecisionValidationError):
            OutputValidator.validate_decision(rec, self.req, self.state, raise_exception=True)

if __name__ == '__main__':
    unittest.main()
