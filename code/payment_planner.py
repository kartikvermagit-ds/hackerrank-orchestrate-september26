"""
Payment Planner Module
----------------------
Generates and simulates candidate payment plans across eligible payment methods:
1. full_payment: Single payment today or on an agreed date.
2. installments: Multi-payment plans matching provider options in request_payment_options.csv.
3. partial_payment: Two-part payment (safe amount today, remainder on earliest full date).
4. wait: Deferred single full payment on earliest safe date.
5. not_recommended: Fallback when no plan is safe.

Financial decision logic will be implemented in subsequent phases.
"""

from typing import List, Optional
from models import EvaluationRequest, PaymentOption, CandidatePlan
from financial_state import FinancialState
from forecast import ForecastEngine

class PaymentPlanner:
    """Scaffolding for generating and evaluating candidate payment schedules."""

    def __init__(self, forecast_engine: ForecastEngine):
        self.forecaster = forecast_engine

    def generate_candidate_plans(self, request: EvaluationRequest,
                                 state: FinancialState,
                                 options: List[PaymentOption],
                                 amount_safe_to_pay: float,
                                 earliest_date_for_full_payment: Optional[str],
                                 spending_changes: Optional[List[str]] = None) -> List[CandidatePlan]:
        """
        Generate candidate payment plans for the request given the user's financial state.

        Args:
            request: Evaluation request.
            state: Reconstructed financial state.
            options: Available provider payment options.
            amount_safe_to_pay: Safe amount today.
            earliest_date_for_full_payment: Earliest safe date without spending changes.
            spending_changes: Proposed spending modifications.

        Returns:
            List of CandidatePlan objects.
        """
        if spending_changes is None:
            spending_changes = []

        plans: List[CandidatePlan] = []

        # Scaffolding stub: check if full payment today is safe
        is_safe_today = (amount_safe_to_pay >= request.requested_amount)
        if 'full_payment' in state.allowed_payment_methods:
            plans.append(CandidatePlan(
                method='full_payment',
                payment_schedule=[(request.request_date, request.requested_amount)],
                spending_changes=spending_changes,
                total_amount=request.requested_amount,
                first_payment_date=request.request_date,
                number_of_payments=1,
                payment_option_id=None,
                is_safe=is_safe_today,
                affordability_status='affordable_now' if is_safe_today else 'not_affordable',
                earliest_date_for_full_payment=request.request_date if is_safe_today else earliest_date_for_full_payment
            ))

        return plans
