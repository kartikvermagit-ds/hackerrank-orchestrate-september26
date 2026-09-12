"""
Safe Amount & Earliest Full Payment Date Calculator
---------------------------------------------------
Calculates:
1. amount_safe_to_pay: Maximum amount safe to commit on request_date before optional
   spending changes, respecting minimum balance and protected expenses (0 <= amt <= requested_amount).
2. earliest_date_for_full_payment: Earliest safe calendar date for a single full payment
   without optional spending changes (equals request_date if safe now, or future payday).

Financial decision logic will be implemented in subsequent phases.
"""

from typing import Optional
from financial_state import FinancialState
from forecast import ForecastEngine

class SafeAmountCalculator:
    """Scaffolding for computing headroom and earliest safe full payment dates."""

    def __init__(self, forecast_engine: ForecastEngine):
        self.forecaster = forecast_engine

    def compute_safe_amount(self, state: FinancialState, request_date: str, requested_amount: float,
                            desired_completion_date: Optional[str] = None) -> float:
        """
        Compute maximum safe payment amount on request_date before optional spending changes.

        Args:
            state: Reconstructed financial state of the user.
            request_date: Evaluation date (YYYY-MM-DD).
            requested_amount: Total requested amount.
            desired_completion_date: Optional deadline date.

        Returns:
            Safe amount float between 0.0 and requested_amount.
        """
        # Scaffolding stub
        headroom = max(0.0, state.liquid_starting_balance - state.minimum_balance_to_keep)
        return min(requested_amount, round(headroom, 2))

    def compute_earliest_date_for_full_payment(self, state: FinancialState, request_date: str,
                                               requested_amount: float,
                                               amount_safe_to_pay: float,
                                               desired_completion_date: Optional[str] = None) -> Optional[str]:
        """
        Find the earliest projected date when a single full payment is safe without spending changes.

        Args:
            state: Reconstructed financial state.
            request_date: Evaluation date.
            requested_amount: Total requested amount.
            amount_safe_to_pay: Safe amount today.
            desired_completion_date: Optional deadline.

        Returns:
            Earliest safe date string (YYYY-MM-DD), or None if never safe within forecast.
        """
        # Scaffolding stub
        if amount_safe_to_pay >= requested_amount:
            return request_date
        return None
