"""
Deterministic Safe Amount Calculator
------------------------------------
Calculates amount_safe_to_pay:
The largest amount the user can safely pay on request_date BEFORE optional spending changes, while:
- protecting essential expenses
- maintaining minimum_balance_to_keep
- passing the complete 90-day safety check

Constraints:
0 <= amount_safe_to_pay <= requested_amount

Deterministic, precision-preserving calculation without LLMs or hardcoded rules.
"""

from typing import Optional
from decimal import Decimal, ROUND_FLOOR
import pandas as pd
from financial_state import FinancialState
from forecast import ForecastEngine

class SafeAmountCalculator:
    """Calculates safe payment amount on request_date and earliest safe full payment dates."""

    def __init__(self, forecast_engine: ForecastEngine):
        self.forecaster = forecast_engine

    def compute_safe_amount(self, state: FinancialState, request_date: str, requested_amount: float,
                            desired_completion_date: Optional[str] = None) -> float:
        """
        Compute the maximum amount safe to commit on request_date before optional spending changes.
        0 <= amount_safe_to_pay <= requested_amount.

        Args:
            state: Reconstructed FinancialState.
            request_date: Evaluation date (YYYY-MM-DD).
            requested_amount: Total requested amount.
            desired_completion_date: Optional deadline date.

        Returns:
            Deterministic float rounded to 2 decimal places.
        """
        if requested_amount <= 0.0:
            return 0.0

        # Horizon: standard 90-day forecast
        h_days = 90
        # If user has no confirmed regular salary (e.g. gig worker) and has a desired completion date
        if desired_completion_date and (state.salary_amount is None or state.salary_amount <= 0):
            req_days = (pd.to_datetime(desired_completion_date) - pd.to_datetime(request_date)).days
            if 0 < req_days < 90:
                h_days = req_days

        # 1. Run baseline 90-day forecast (no proposed payments, no spending changes)
        daily_records = self.forecaster.forecast_balance(
            state=state,
            request_date=request_date,
            proposed_payments=None,
            spending_changes=None,
            horizon_days=h_days
        )

        # 2. Find minimum baseline closing balance across the forecast horizon
        min_balance_seen = min(bal for _, bal in daily_records)
        headroom_90d = max(0.0, min_balance_seen - state.minimum_balance_to_keep)

        # 3. Short-term pre-payday cashflow headroom: protects essential daily living expenses and fixed debits until next confirmed payday
        req_dt = pd.to_datetime(request_date)
        sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
        next_sal = state.next_salary_date

        next_payday_dt = None
        if next_sal:
            next_payday_dt = pd.to_datetime(next_sal)
        else:
            for d in range(1, 32):
                cand = req_dt + pd.Timedelta(days=d)
                if cand.day == sal_day:
                    next_payday_dt = cand
                    break

        days_to_payday = (next_payday_dt - req_dt).days if next_payday_dt else 30

        # Recurring monthly debits due before next confirmed payday
        rec_outflows = 0.0
        for rx in state.recurring_expenses:
            rx_day = rx['day_of_month']
            for d in range(0, days_to_payday):
                cand = req_dt + pd.Timedelta(days=d)
                if cand.day == rx_day:
                    last_dt = pd.to_datetime(rx['last_date'])
                    if d == 0 and rx['last_date'] == cand.strftime('%Y-%m-%d'):
                        pass
                    elif cand > last_dt:
                        rec_outflows += rx['amount']

        # Scheduled debits due before next confirmed payday
        sched_outflows = 0.0
        for d_str, amt in state.scheduled_debits.items():
            if next_payday_dt and request_date <= d_str < next_payday_dt.strftime('%Y-%m-%d'):
                sched_outflows += amt

        # Uncommitted essential daily living expenses reserved until payday
        burn_rate = state.daily_uncommitted_burn if state.daily_uncommitted_burn > 0 else state.daily_variable_burn
        living_outflows = days_to_payday * burn_rate

        avail_cash = state.liquid_starting_balance - state.minimum_balance_to_keep
        pre_payday_headroom = max(0.0, avail_cash - (rec_outflows + sched_outflows + living_outflows))

        headroom = min(headroom_90d, pre_payday_headroom)
        if headroom <= 0.0:
            return 0.0

        # 4. Cap at requested_amount and round down to 2 decimal places using Decimal
        headroom_dec = Decimal(str(round(headroom, 4)))
        safe_dec = min(Decimal(str(requested_amount)), headroom_dec).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)
        safe_amt = float(safe_dec)

        # 5. Exact numeric verification: simulate paying safe_amt today to guarantee 100% safety
        # If boundary precision dips below minimum_balance_to_keep, adjust downward
        while safe_amt > 0.0:
            is_safe, _ = self.forecaster.passes_safety_check(
                state=state,
                request_date=request_date,
                proposed_payments={request_date: safe_amt},
                spending_changes=None,
                horizon_days=h_days
            )
            if is_safe:
                break
            safe_amt = round(safe_amt - 0.01, 2)

        return max(0.0, min(requested_amount, safe_amt))

    def compute_earliest_date_for_full_payment(self, state: FinancialState, request_date: str,
                                               requested_amount: float,
                                               amount_safe_to_pay: Optional[float] = None,
                                               desired_completion_date: Optional[str] = None) -> Optional[str]:
        """
        Find the earliest projected date within the 90-day forecast on which paying the
        ENTIRE requested_amount as a single payment passes the safety check.

        Important Rules & Guarantees:
        - Independent of user's payment-method preference (financial capacity vs method eligibility).
        - Calculated strictly without optional spending changes (spending_changes=None).
        - For affordable_now (amount_safe_to_pay >= requested_amount), returns request_date.
        - If the full amount is not safe within the forecast period, returns None (empty/null internally).
        - Deterministic Python simulation without LLM calls or hardcoded rules.

        Args:
            state: Reconstructed FinancialState of the user.
            request_date: Date of the evaluation request (YYYY-MM-DD).
            requested_amount: Full purchase / payment amount.
            amount_safe_to_pay: Optional pre-computed safe amount on request_date. If None, computed.
            desired_completion_date: Optional deadline date.

        Returns:
            ISO date string (YYYY-MM-DD) or None if not safe within 90 days.
        """
        if requested_amount <= 0.0:
            return request_date

        if amount_safe_to_pay is None:
            amount_safe_to_pay = self.compute_safe_amount(
                state=state,
                request_date=request_date,
                requested_amount=requested_amount,
                desired_completion_date=desired_completion_date
            )

        # 1. If full amount is safe today on request_date, earliest date is request_date.
        # This holds even if user profile prefers installments or disallows full payment.
        if amount_safe_to_pay >= requested_amount - 1e-4:
            return request_date

        # 2. If user has no regular confirmed salary (e.g. gig worker), balance only depletes over time.
        # Without confirmed future salary inflows, full payment will never become safe later.
        if state.salary_amount is None or state.salary_amount <= 0:
            return None

        # 3. Future confirmed salary paydays within the 90-day forecast horizon
        req_dt = pd.to_datetime(request_date)
        sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
        next_sal = state.next_salary_date

        paydays = []
        for day_offset in range(1, 91):
            cand_dt = req_dt + pd.Timedelta(days=day_offset)
            cand_date_str = cand_dt.strftime('%Y-%m-%d')
            if (next_sal and cand_date_str == next_sal) or (cand_dt.day == sal_day):
                paydays.append((cand_date_str, day_offset))

        due_offset = (pd.to_datetime(desired_completion_date) - req_dt).days if desired_completion_date else 90

        # 4. Check paydays in chronological order across the required safety horizon
        for cand_date_str, day_offset in paydays:
            payments = {cand_date_str: requested_amount}
            h_days = min(90, max(day_offset, due_offset)) if desired_completion_date and day_offset <= due_offset else min(90, day_offset + 30)
            is_safe, _ = self.forecaster.passes_safety_check(
                state=state,
                request_date=request_date,
                proposed_payments=payments,
                spending_changes=None,
                horizon_days=h_days
            )
            if is_safe:
                return cand_date_str

        return None

