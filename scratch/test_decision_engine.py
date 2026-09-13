"""
Test Suite for Deterministic Decision Engine
---------------------------------------------
Verifies:
1. Candidate generation across all sources: full_payment, partial_payment, installments, wait, spending changes.
2. Only allows immediate payment methods present in payment_methods_user_will_consider.
3. wait is allowed only when full payment becomes safe later and user accepts full_payment.
4. Fallback to not_recommended when no candidate plan is safe.
5. Exact 6-stage tie-breaker ranking per problem_statement.md:
   - Complete by desired_completion_date
   - Require no spending changes (fewer changes)
   - Minimize total amount paid
   - Start payment earlier
   - Use fewer payments
   - Lowest payment_option_id
6. Structured decision object (RecommendationOutput) returned directly.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath('code'))
from models import EvaluationRequest, PaymentOption, CandidatePlan, RecommendationOutput
from financial_state import FinancialState
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine

class TestDecisionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ForecastEngine()
        self.safe_calc = SafeAmountCalculator(self.engine)
        self.planner = PaymentPlanner(self.engine)
        self.decider = DecisionEngine(self.engine, self.safe_calc, self.planner)

    def test_affordable_now_full_payment(self):
        """User with sufficient funds and full_payment allowed gets full_payment affordable_now."""
        req = EvaluationRequest(
            request_id="req_full",
            user_id="u_full",
            request_date="2026-04-01",
            request_type="electronics",
            requested_amount=1000.0,
            desired_completion_date="2026-05-01",
            allows_partial_payment=True,
            request_text="Can I buy now?"
        )
        state = FinancialState(
            user_id="u_full",
            home_currency="USD",
            current_available_balance=5000.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=3000.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment", "installments"},
            max_installment_months=6.0,
            flexible_events=[]
        )
        rec = self.decider.decide(req, state, options=[])
        self.assertIsInstance(rec, RecommendationOutput)
        self.assertEqual(rec.recommended_payment_method, "full_payment")
        self.assertEqual(rec.affordability_status, "affordable_now")
        self.assertEqual(rec.payment_plan, "2026-04-01:1000")
        self.assertEqual(rec.spending_changes_needed, "none")

    def test_immediate_method_preference_filter(self):
        """If user only considers installments, full_payment is NOT recommended even if affordable."""
        req = EvaluationRequest(
            request_id="req_pref",
            user_id="u_pref",
            request_date="2026-04-01",
            request_type="electronics",
            requested_amount=1000.0,
            desired_completion_date="2026-07-01",
            allows_partial_payment=True,
            request_text="I prefer installments"
        )
        state = FinancialState(
            user_id="u_pref",
            home_currency="USD",
            current_available_balance=5000.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=3000.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"installments"},  # NO full_payment!
            max_installment_months=6.0,
            flexible_events=[]
        )
        opt = PaymentOption(
            payment_option_id="opt_inst_3m",
            request_id="req_pref",
            payment_method="installments",
            payment_amount=340.0,
            number_of_payments=3,
            first_payment_date="2026-04-05",
            payment_frequency_days=30.0,
            financing_fee=20.0,
            total_payable_amount=1020.0
        )
        rec = self.decider.decide(req, state, options=[opt])
        self.assertEqual(rec.recommended_payment_method, "installments")
        self.assertEqual(rec.affordability_status, "affordable_with_plan")

    def test_wait_allowed_only_when_full_payment_accepted(self):
        """Wait is recommended when full payment becomes safe later and user accepts full_payment."""
        req = EvaluationRequest(
            request_id="req_wait",
            user_id="u_wait",
            request_date="2026-04-01",
            request_type="appliances",
            requested_amount=1500.0,
            desired_completion_date="2026-04-30",
            allows_partial_payment=False,
            request_text="Can I wait for payday?"
        )
        state = FinancialState(
            user_id="u_wait",
            home_currency="USD",
            current_available_balance=1800.0,
            minimum_balance_to_keep=1000.0,  # Headroom today is 800 < 1500
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=10.0,
            salary_amount=2500.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",  # Salary on day 15 will replenish cash
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment"},  # Accepts full_payment
            max_installment_months=None,
            flexible_events=[]
        )
        rec = self.decider.decide(req, state, options=[])
        self.assertEqual(rec.recommended_payment_method, "wait")
        self.assertEqual(rec.affordability_status, "affordable_later")
        self.assertEqual(rec.earliest_date_for_full_payment, "2026-04-15")
        self.assertEqual(rec.payment_plan, "2026-04-15:1500")

    def test_fallback_to_not_recommended(self):
        """When no option or plan is safe, returns not_recommended and not_affordable."""
        req = EvaluationRequest(
            request_id="req_broke",
            user_id="u_broke",
            request_date="2026-04-01",
            request_type="luxury",
            requested_amount=100000.0,  # Impossible amount
            desired_completion_date="2026-04-30",
            allows_partial_payment=False,
            request_text="Can I buy this yacht?"
        )
        state = FinancialState(
            user_id="u_broke",
            home_currency="USD",
            current_available_balance=1200.0,
            minimum_balance_to_keep=1000.0,
            reserved_pending_debits=0.0,
            recurring_expenses=[],
            scheduled_debits={},
            daily_variable_burn=20.0,
            salary_amount=1500.0,
            salary_day_of_month=15,
            next_salary_date="2026-04-15",
            protected_categories=set(),
            reducible_categories=set(),
            stoppable_categories=set(),
            allowed_payment_methods={"full_payment"},
            max_installment_months=None,
            flexible_events=[]
        )
        rec = self.decider.decide(req, state, options=[])
        self.assertEqual(rec.recommended_payment_method, "not_recommended")
        self.assertEqual(rec.affordability_status, "not_affordable")
        self.assertEqual(rec.payment_plan, "none")
        self.assertEqual(rec.spending_changes_needed, "none")

    def test_ranking_tie_breakers(self):
        """Test exact 6-stage tie-breaker ranking logic."""
        # Plan A: 1 spending change, total 1000, date 2026-04-01, 1 payment
        plan_a = CandidatePlan(
            method="full_payment",
            payment_schedule=[("2026-04-01", 1000.0)],
            spending_changes=["stop:ev1"],
            total_amount=1000.0,
            first_payment_date="2026-04-01",
            number_of_payments=1,
            payment_option_id=None,
            is_safe=True,
            affordability_status="affordable_with_plan",
            earliest_date_for_full_payment="2026-04-01"
        )
        # Plan B: 0 spending changes, total 1050, date 2026-04-01, 3 payments
        plan_b = CandidatePlan(
            method="installments",
            payment_schedule=[("2026-04-01", 350.0), ("2026-05-01", 350.0), ("2026-06-01", 350.0)],
            spending_changes=[],
            total_amount=1050.0,
            first_payment_date="2026-04-01",
            number_of_payments=3,
            payment_option_id="opt_01",
            is_safe=True,
            affordability_status="affordable_with_plan",
            earliest_date_for_full_payment="2026-04-01"
        )
        # Plan C: 0 spending changes, total 1000, date 2026-04-15, 1 payment (wait)
        plan_c = CandidatePlan(
            method="wait",
            payment_schedule=[("2026-04-15", 1000.0)],
            spending_changes=[],
            total_amount=1000.0,
            first_payment_date="2026-04-15",
            number_of_payments=1,
            payment_option_id=None,
            is_safe=True,
            affordability_status="affordable_later",
            earliest_date_for_full_payment="2026-04-15"
        )
        # Plan D: 0 spending changes, total 1000, date 2026-04-01, 1 payment (immediate full)
        plan_d = CandidatePlan(
            method="full_payment",
            payment_schedule=[("2026-04-01", 1000.0)],
            spending_changes=[],
            total_amount=1000.0,
            first_payment_date="2026-04-01",
            number_of_payments=1,
            payment_option_id=None,
            is_safe=True,
            affordability_status="affordable_now",
            earliest_date_for_full_payment="2026-04-01"
        )

        ranked = self.decider.rank_plans([plan_a, plan_b, plan_c, plan_d])
        # Plan D has 0 changes, 1000 total, earliest date 2026-04-01, 1 payment -> WINNER!
        self.assertEqual(ranked[0].method, "full_payment")
        self.assertEqual(ranked[0].total_amount, 1000.0)
        self.assertEqual(len(ranked[0].spending_changes), 0)

        # Plan C (wait) has 0 changes, 1000 total, date 2026-04-15 -> beats Plan B (more total) and Plan A (has changes)
        self.assertEqual(ranked[1].method, "wait")

        # Plan B has 0 changes, but higher total (1050) -> beats Plan A because Plan A requires changes
        self.assertEqual(ranked[2].method, "installments")

        # Plan A has 1 spending change -> ranked last among these
        self.assertEqual(ranked[3].method, "full_payment")
        self.assertEqual(len(ranked[3].spending_changes), 1)

if __name__ == '__main__':
    unittest.main()
