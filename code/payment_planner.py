"""
Payment Planner & Option Evaluation Engine
------------------------------------------
Evaluates provider payment options from dataset/request_payment_options.csv and generates
candidate payment plans across all allowed methods:
1. installments: Multi-payment provider options from request_payment_options.csv
2. full_payment: Immediate full payment on request_date
3. partial_payment: Two-part payment (safe amount today, remainder on earliest safe date)
4. wait: Deferred single full payment on earliest safe date

Core Evaluation Rules:
- Retrieves all supplied provider payment options for the request.
- Respects payment start date (first_payment_date).
- Respects recurring payment interval (payment_frequency_days).
- Respects number of payments (number_of_payments).
- Respects financing fees (financing_fee) and total payable amount (total_payable_amount).
- Respects user's payment_methods_user_will_consider.
- Respects max_installment_months where applicable.
- Simulates every eligible option through the deterministic 90-day cashflow forecast.
- Safety check verifies:
  * every payment can be made without violating minimum_balance_to_keep
  * essential expenses and living costs remain covered throughout
  * the request completes by desired_completion_date
- Strictly reproduces supplied options without inventing schedules.
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd

from models import EvaluationRequest, PaymentOption, CandidatePlan
from financial_state import FinancialState
from forecast import ForecastEngine

class PaymentPlanner:
    """Evaluates provider payment options and generates candidate payment plans."""

    def __init__(self, forecast_engine: ForecastEngine):
        self.forecaster = forecast_engine

    @staticmethod
    def format_payment_schedule(schedule: List[Tuple[str, float]]) -> str:
        """
        Format a payment schedule into the standard string:
        YYYY-MM-DD:amount|YYYY-MM-DD:amount... or 'none'.
        """
        if not schedule:
            return "none"

        def fmt_amt(val: float) -> str:
            if float(val).is_integer():
                return f"{int(val)}"
            return f"{float(val):.2f}"

        return "|".join(f"{dt}:{fmt_amt(amt)}" for dt, amt in schedule)

    def evaluate_installment_option(self, option: PaymentOption,
                                   request: EvaluationRequest,
                                   state: FinancialState,
                                   spending_changes: Optional[List[str]] = None,
                                   earliest_date_for_full_payment: Optional[str] = None) -> Optional[CandidatePlan]:
        """
        Evaluate a single installment option from request_payment_options.csv.

        Returns CandidatePlan if the option matches tenure constraints and user preferences,
        with is_safe indicating whether all payments can be made safely by desired_completion_date.
        Returns None if ineligible due to user payment preferences or tenure limits.
        """
        if option.payment_method != 'installments':
            return None

        # 1. Respect user's payment_methods_user_will_consider
        if 'installments' not in state.allowed_payment_methods:
            return None

        # 2. Respect max_installment_months where applicable
        freq_days = option.payment_frequency_days if option.payment_frequency_days else 30.0
        if state.max_installment_months is not None:
            total_duration_days = (option.number_of_payments - 1) * freq_days
            total_duration_months = total_duration_days / 30.0
            if total_duration_months > state.max_installment_months and option.number_of_payments > state.max_installment_months:
                return None

        # 3. Construct chronological schedule strictly matching the option
        first_dt = pd.to_datetime(option.first_payment_date)
        inst_sched: List[Tuple[str, float]] = []
        payments_dict: Dict[str, float] = {}

        for i in range(option.number_of_payments):
            inst_dt = first_dt + timedelta(days=int(i * freq_days))
            inst_date_str = inst_dt.strftime('%Y-%m-%d')
            inst_sched.append((inst_date_str, option.payment_amount))
            payments_dict[inst_date_str] = payments_dict.get(inst_date_str, 0.0) + option.payment_amount

        # 4. Verify request completes by desired_completion_date
        last_payment_date = inst_sched[-1][0]
        finishes_by_deadline = (last_payment_date <= request.desired_completion_date)

        # 5. Simulate through the deterministic cash flow forecast
        req_dt = pd.to_datetime(request.request_date)
        last_dt = pd.to_datetime(last_payment_date)
        h_days = max(1, min(90, (last_dt - req_dt).days))

        is_safe, min_bal_seen = self.forecaster.passes_safety_check(
            state=state,
            request_date=request.request_date,
            proposed_payments=payments_dict,
            spending_changes=spending_changes,
            horizon_days=h_days
        )

        is_plan_safe = (is_safe and finishes_by_deadline)
        status = 'affordable_with_plan' if is_plan_safe else 'not_affordable'

        return CandidatePlan(
            method='installments',
            payment_schedule=inst_sched,
            spending_changes=list(spending_changes) if spending_changes else [],
            total_amount=option.total_payable_amount,
            first_payment_date=option.first_payment_date,
            number_of_payments=option.number_of_payments,
            payment_option_id=option.payment_option_id,
            is_safe=is_plan_safe,
            affordability_status=status,
            earliest_date_for_full_payment=earliest_date_for_full_payment
        )

    def evaluate_all_installment_options(self, options: List[PaymentOption],
                                         request: EvaluationRequest,
                                         state: FinancialState,
                                         spending_changes: Optional[List[str]] = None,
                                         earliest_date_for_full_payment: Optional[str] = None) -> List[CandidatePlan]:
        """Evaluate all installment options supplied in request_payment_options.csv for this request."""
        plans: List[CandidatePlan] = []
        for opt in options:
            if opt.payment_method == 'installments':
                plan = self.evaluate_installment_option(
                    option=opt,
                    request=request,
                    state=state,
                    spending_changes=spending_changes,
                    earliest_date_for_full_payment=earliest_date_for_full_payment
                )
                if plan is not None:
                    plans.append(plan)
        return plans

    def evaluate_partial_payment_plan(self, request: EvaluationRequest,
                                      state: FinancialState,
                                      amount_safe_to_pay: float,
                                      earliest_date_for_full_payment: Optional[str],
                                      spending_changes: Optional[List[str]] = None) -> Optional[CandidatePlan]:
        """
        Evaluate partial-payment planning according to problem_statement.md.

        Partial payment is eligible ONLY when:
        - allows_partial_payment == True (request allows it)
        - user accepts partial_payment ('partial_payment' in state.allowed_payment_methods)
        - 0 < amount_safe_to_pay < requested_amount
        - earliest_date_for_full_payment <= desired_completion_date
        - evaluated without optional spending changes

        The plan MUST contain exactly two payments:
        1. request_date : amount_safe_to_pay
        2. earliest_date_for_full_payment : remaining amount (requested_amount - amount_safe_to_pay)

        The two payments must sum exactly to requested_amount.
        The complete plan is validated through the 90-day forecast.
        """
        # 1. Eligibility preconditions
        if not request.allows_partial_payment:
            return None

        if 'partial_payment' not in state.allowed_payment_methods:
            return None

        req_amt = request.requested_amount
        if not (0.0 < amount_safe_to_pay < req_amt):
            return None

        if earliest_date_for_full_payment is None:
            return None

        if earliest_date_for_full_payment > request.desired_completion_date:
            return None

        # Partial payment is evaluated before spending changes per challenge contract
        if spending_changes:
            return None

        # 2. Exactly two payments summing to requested_amount
        first_payment = round(amount_safe_to_pay, 2)
        second_payment = round(req_amt - first_payment, 2)

        # Numerical integrity check
        if abs((first_payment + second_payment) - req_amt) > 0.01:
            second_payment = round(req_amt - first_payment, 2)

        part_sched = [
            (request.request_date, first_payment),
            (earliest_date_for_full_payment, second_payment)
        ]
        payments_dict = {
            request.request_date: first_payment,
            earliest_date_for_full_payment: second_payment
        }

        # 3. Validate the complete plan through the 90-day forecast
        is_safe, min_bal = self.forecaster.passes_safety_check(
            state=state,
            request_date=request.request_date,
            proposed_payments=payments_dict,
            spending_changes=None,
            horizon_days=90
        )

        return CandidatePlan(
            method='partial_payment',
            payment_schedule=part_sched,
            spending_changes=[],
            total_amount=req_amt,
            first_payment_date=request.request_date,
            number_of_payments=2,
            payment_option_id=None,
            is_safe=is_safe,
            affordability_status='affordable_with_plan' if is_safe else 'not_affordable',
            earliest_date_for_full_payment=earliest_date_for_full_payment
        )

    def generate_candidate_plans(self, request: EvaluationRequest,
                                 state: FinancialState,
                                 options: List[PaymentOption],
                                 amount_safe_to_pay: float,
                                 earliest_date_for_full_payment: Optional[str],
                                 spending_changes: Optional[List[str]] = None) -> List[CandidatePlan]:
        """
        Generate all candidate plans (full payment, installments, partial payment, wait)
        given the user's financial state and spending adjustments.
        """
        if spending_changes is None:
            spending_changes = []

        plans: List[CandidatePlan] = []
        req_amt = request.requested_amount
        req_date = request.request_date
        due_date = request.desired_completion_date

        # 1. Full Payment Candidate
        if 'full_payment' in state.allowed_payment_methods:
            if not spending_changes:
                is_safe = (amount_safe_to_pay >= req_amt - 1e-4) and (req_date <= due_date)
            else:
                payments_dict = {req_date: req_amt}
                is_safe, _ = self.forecaster.passes_safety_check(
                    state=state,
                    request_date=req_date,
                    proposed_payments=payments_dict,
                    spending_changes=spending_changes,
                    horizon_days=90
                )
            finishes_in_time = (req_date <= due_date)
            status = 'affordable_now' if (is_safe and not spending_changes) else ('affordable_with_plan' if is_safe else 'not_affordable')

            plans.append(CandidatePlan(
                method='full_payment',
                payment_schedule=[(req_date, req_amt)],
                spending_changes=list(spending_changes),
                total_amount=req_amt,
                first_payment_date=req_date,
                number_of_payments=1,
                payment_option_id=None,
                is_safe=(is_safe and finishes_in_time),
                affordability_status=status,
                earliest_date_for_full_payment=req_date if (is_safe and not spending_changes) else earliest_date_for_full_payment
            ))

        # 2. Partial Payment Candidate
        partial_plan = self.evaluate_partial_payment_plan(
            request=request,
            state=state,
            amount_safe_to_pay=amount_safe_to_pay,
            earliest_date_for_full_payment=earliest_date_for_full_payment,
            spending_changes=spending_changes
        )
        if partial_plan is not None and partial_plan.is_safe:
            plans.append(partial_plan)

        # 3. Installment Options from request_payment_options.csv
        installment_plans = self.evaluate_all_installment_options(
            options=options,
            request=request,
            state=state,
            spending_changes=spending_changes,
            earliest_date_for_full_payment=earliest_date_for_full_payment
        )
        plans.extend(installment_plans)


        # 4. Wait Candidate
        if (not spending_changes and
            'full_payment' in state.allowed_payment_methods and
            earliest_date_for_full_payment is not None and
            earliest_date_for_full_payment <= due_date and
            earliest_date_for_full_payment > req_date):

            wait_sched = [(earliest_date_for_full_payment, req_amt)]
            payments_dict = {earliest_date_for_full_payment: req_amt}
            h_days = (pd.to_datetime(earliest_date_for_full_payment) - pd.to_datetime(req_date)).days

            is_safe, _ = self.forecaster.passes_safety_check(
                state=state,
                request_date=req_date,
                proposed_payments=payments_dict,
                spending_changes=[],
                horizon_days=h_days
            )
            if is_safe:
                plans.append(CandidatePlan(
                    method='wait',
                    payment_schedule=wait_sched,
                    spending_changes=[],
                    total_amount=req_amt,
                    first_payment_date=earliest_date_for_full_payment,
                    number_of_payments=1,
                    payment_option_id=None,
                    is_safe=True,
                    affordability_status='affordable_later',
                    earliest_date_for_full_payment=earliest_date_for_full_payment
                ))

        return plans
