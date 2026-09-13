import os
import sys
import unittest
import pandas as pd

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
code_dir = os.path.join(repo_root, 'code')
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner
from decision_engine import DecisionEngine
from models import EvaluationRequest, FinancialProfile, PaymentOption

class TestRegressionFourPatterns(unittest.TestCase):
    """
    Regression test suite covering the 4 systematic failure patterns identified during evaluation:
    1. Unconfirmed commission/bonus messages must never override settled base salary.
    2. amount_safe_to_pay must protect uncommitted essential living spend before next payday.
    3. Deferred earliest_date_for_full_payment evaluated conservatively across forecast horizon.
    4. Spending changes must strictly respect user category preferences and deadline prioritization.
    """

    @classmethod
    def setUpClass(cls):
        dataset_dir = os.path.join(repo_root, 'dataset')
        cls.loader = DataLoader(dataset_dir)
        cls.profiles = cls.loader.load_profiles()
        cls.events = cls.loader.load_events()
        cls.payment_options = cls.loader.load_payment_options()
        cls.messages = cls.loader.load_messages()
        cls.rates = cls.loader.load_exchange_rates()

        cls.msg_proc = MessageProcessor(cls.messages)
        cls.normalizer = EventNormalizer(cls.rates, cls.msg_proc)
        cls.context_builder = ContextBuilder(cls.profiles, cls.events, cls.payment_options, cls.normalizer)
        cls.forecaster = ForecastEngine()
        cls.safe_calc = SafeAmountCalculator(cls.forecaster)
        cls.planner = PaymentPlanner(cls.forecaster)
        cls.engine = DecisionEngine(cls.forecaster, cls.safe_calc, cls.planner)

    def test_pattern_1_unconfirmed_commission_rejected(self):
        """Pattern 1: Unconfirmed commission in employer messages must not inflate confirmed base salary."""
        # Message 08 references user_11 with unapproved sales commission
        user_id = 'user_11'
        u_events = self.events[user_id]
        sal_amt, sal_day, next_sal = self.normalizer.get_salary_info(user_id, u_events, '2025-05-03')
        # Base settled salary is IDR 23,256,000; unconfirmed commission message must not inflate it to 38,760,000
        self.assertEqual(sal_amt, 23256000.0)
        self.assertEqual(sal_day, 15)

    def test_pattern_2_prepayday_living_burn_reserved(self):
        """Pattern 2: amount_safe_to_pay must protect uncommitted essential living expenses before payday."""
        # Check user 21 who has available cash but living expenses before April 15 payday
        req = EvaluationRequest(
            request_id='test_p2',
            user_id='user_21',
            request_date='2026-04-03',
            request_type='education',
            requested_amount=2000.0,
            desired_completion_date='2026-04-14',
            allows_partial_payment=False,
            request_text='Can I pay 2000 today?'
        )
        state, _ = self.context_builder.build_context(req)
        safe_amt = self.safe_calc.compute_safe_amount(state, req.request_date, req.requested_amount)
        # Starting liquid cash above minimum balance is 2058.35, but safe amount must be strictly lower
        # to protect pre-payday living burn and recurring debits before April 15
        self.assertLess(safe_amt, state.liquid_starting_balance - state.minimum_balance_to_keep)
        self.assertGreater(safe_amt, 0.0)

    def test_pattern_3_deferred_full_payment_horizon(self):
        """Pattern 3: earliest_date_for_full_payment safely evaluates deferred paydays across forecast horizon."""
        req = EvaluationRequest(
            request_id='test_p3',
            user_id='user_13',
            request_date='2024-03-07',
            request_type='travel',
            requested_amount=941.60,
            desired_completion_date='2024-05-15',
            allows_partial_payment=False,
            request_text='Can I pay travel cost?'
        )
        state, _ = self.context_builder.build_context(req)
        safe_amt = self.safe_calc.compute_safe_amount(state, req.request_date, req.requested_amount)
        earliest_date = self.safe_calc.compute_earliest_date_for_full_payment(
            state, req.request_date, req.requested_amount,
            amount_safe_to_pay=safe_amt,
            desired_completion_date=req.desired_completion_date
        )
        # Cannot pay in full today on 2024-03-07, earliest safe date is confirmed payday on 2024-05-15
        self.assertEqual(earliest_date, '2024-05-15')

    def test_pattern_4_spending_change_category_preferences(self):
        """Pattern 4: Spending changes must strictly respect user category preferences and prioritize deadline."""
        req = EvaluationRequest(
            request_id='test_p4',
            user_id='user_06',
            request_date='2026-01-03',
            request_type='investment',
            requested_amount=620.40,
            desired_completion_date='2026-01-14',
            allows_partial_payment=False,
            request_text='Can I invest 620.40 before Jan 14?'
        )
        state, options = self.context_builder.build_context(req)
        rec = self.engine.decide(req, state, options)
        # User 06 is willing to stop streaming (event_476), enabling on-time full payment today
        self.assertEqual(rec.affordability_status, 'affordable_with_plan')
        self.assertEqual(rec.recommended_payment_method, 'full_payment')
        self.assertEqual(rec.spending_changes_needed, 'stop:event_476')

if __name__ == '__main__':
    unittest.main()
