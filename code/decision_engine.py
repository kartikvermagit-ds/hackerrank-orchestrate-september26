"""
Decision Engine Module
----------------------
Coordinates:
1. Headroom and safe date calculation.
2. Candidate plan generation without spending changes.
3. Candidate plan ranking via 6-stage tie-breaker rules:
   - Complete by desired_completion_date
   - Require no spending changes
   - Minimize total amount paid
   - Start payment earlier
   - Use fewer payments
   - Lowest payment_option_id
4. Combinatorial flexible spending adjustments search when needed.
5. Final RecommendationOutput formatting and explanation synthesis.

Financial decision logic will be implemented in subsequent phases.
"""

from typing import List, Optional
from models import EvaluationRequest, PaymentOption, CandidatePlan, RecommendationOutput
from financial_state import FinancialState
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner

class DecisionEngine:
    """Scaffolding for the multi-stage financial decision engine."""

    def __init__(self, forecast_engine: ForecastEngine,
                 safe_calc: SafeAmountCalculator,
                 planner: PaymentPlanner):
        self.forecaster = forecast_engine
        self.safe_calc = safe_calc
        self.planner = planner

    def rank_plans(self, plans: List[CandidatePlan]) -> List[CandidatePlan]:
        """
        Rank candidate plans per challenge tie-breaker rules.
        """
        def sort_key(p: CandidatePlan):
            num_changes = len(p.spending_changes)
            tot_amt = round(p.total_amount, 2)
            first_date = p.first_payment_date if p.first_payment_date else "9999-99-99"
            num_payments = p.number_of_payments
            opt_id = p.payment_option_id if p.payment_option_id else "zzzzzz"
            return (num_changes, tot_amt, first_date, num_payments, opt_id)

        return sorted(plans, key=sort_key)

    def generate_explanation(self, plan: CandidatePlan, request: EvaluationRequest,
                             state: FinancialState, amount_safe_to_pay: float) -> str:
        """
        Synthesize concise grounded explanation for the recommendation.
        """
        curr = state.home_currency
        req_str = f"{curr} {request.requested_amount:,.2f}".replace('.00', '')
        min_str = f"{curr} {state.minimum_balance_to_keep:,.2f}".replace('.00', '')

        if plan.is_safe and plan.method == 'full_payment':
            return f"Pay {req_str} today. This leaves at least {min_str} available over the next 90 days."
        return f"Do not make this payment today. Safe headroom is currently {curr} {amount_safe_to_pay:,.2f}."

    def decide(self, request: EvaluationRequest, state: FinancialState,
               options: List[PaymentOption]) -> RecommendationOutput:
        """
        Determine the optimal financial recommendation for a user request.

        Args:
            request: Evaluation request.
            state: Reconstructed financial state.
            options: Available payment options.

        Returns:
            Formatted RecommendationOutput object.
        """
        amount_safe = self.safe_calc.compute_safe_amount(
            state, request.request_date, request.requested_amount, request.desired_completion_date
        )
        earliest_date = self.safe_calc.compute_earliest_date_for_full_payment(
            state, request.request_date, request.requested_amount, amount_safe, request.desired_completion_date
        )

        plans = self.planner.generate_candidate_plans(
            request, state, options, amount_safe, earliest_date, spending_changes=[]
        )
        safe_plans = [p for p in plans if p.is_safe]

        if safe_plans:
            winning_plan = self.rank_plans(safe_plans)[0]
        else:
            winning_plan = CandidatePlan(
                method='not_recommended',
                payment_schedule=[],
                spending_changes=[],
                total_amount=0.0,
                first_payment_date=None,
                number_of_payments=0,
                payment_option_id=None,
                is_safe=False,
                affordability_status='not_affordable',
                earliest_date_for_full_payment=earliest_date
            )

        plan_str = "none"
        if winning_plan.payment_schedule:
            def fmt_amt(val):
                return f"{int(val)}" if float(val).is_integer() else f"{float(val):.2f}"
            plan_str = "|".join(f"{dt}:{fmt_amt(amt)}" for dt, amt in winning_plan.payment_schedule)

        changes_str = "|".join(winning_plan.spending_changes) if winning_plan.spending_changes else "none"
        earliest_str = winning_plan.earliest_date_for_full_payment if winning_plan.earliest_date_for_full_payment else ""
        explanation = self.generate_explanation(winning_plan, request, state, amount_safe)

        return RecommendationOutput(
            request_id=request.request_id,
            amount_safe_to_pay=amount_safe,
            affordability_status=winning_plan.affordability_status,
            recommended_payment_method=winning_plan.method,
            payment_plan=plan_str,
            earliest_date_for_full_payment=earliest_str,
            spending_changes_needed=changes_str,
            decision_explanation=explanation
        )
