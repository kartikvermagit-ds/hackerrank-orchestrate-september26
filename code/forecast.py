"""
Deterministic 90-Day Financial Forecast Engine
-----------------------------------------------
Simulates continuous daily cash flow and account balance over a 90-day forecast horizon.

Core Principles & Rules:
- Starts from user's current available balance (net of reserved pending debits).
- Simulates from request_date through 90 days (request_date to request_date + 90 days).
- Inflows:
  - Confirmed recurring salary credited on regular payday (day of month).
  - First upcoming confirmed salary applied strictly on its scheduled settlement date.
  - Variable gig earnings, unconfirmed bonuses, commissions, and windfalls are ignored.
- Outflows:
  - Recurring monthly fixed debits applied on their recurring day of month.
  - Accounts for spending adjustments (stop:<id>, reduce_to:<id>:<amount>).
  - Scheduled future debits applied on their settlement dates.
  - Essential variable living burn (groceries, transport, dining) applied daily.
  - Arbitrary proposed payment schedules applied on designated calendar dates.
- Safety:
  - Verifies balance >= minimum_balance_to_keep at every calendar day across the horizon.
  - Ignores pending credits, failed transactions, cancelled transactions, duplicate records,
    and unrealized investment valuations.
- 100% deterministic Python arithmetic with zero LLM calls.
"""

from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime, timedelta
import pandas as pd
from financial_state import FinancialState

class ForecastEngine:
    """Deterministic daily cashflow and balance simulator."""

    def __init__(self):
        pass

    def forecast_balance(self, state: FinancialState, request_date: str,
                         proposed_payments: Optional[Dict[str, float]] = None,
                         spending_changes: Optional[List[str]] = None,
                         horizon_days: int = 90) -> List[Tuple[str, float]]:
        """
        Forecast daily account balances over horizon_days starting from request_date.

        Args:
            state: Reconstructed FinancialState of the user.
            request_date: Evaluation date (YYYY-MM-DD).
            proposed_payments: Optional mapping of date (YYYY-MM-DD) to payment amount.
            spending_changes: Optional list of spending modifications (e.g. stop:id, reduce_to:id:amt).
            horizon_days: Number of forecast days (default: 90).

        Returns:
            List of (date_str, closing_balance) tuples for each day in [request_date, request_date + horizon_days].
        """
        if proposed_payments is None:
            proposed_payments = {}
        if spending_changes is None:
            spending_changes = []

        # Parse spending changes
        stopped_event_ids: Set[str] = set()
        reduced_amounts: Dict[str, float] = {}

        for change in spending_changes:
            if change.startswith('stop:'):
                ev_id = change.split(':', 1)[1].strip()
                stopped_event_ids.add(ev_id)
            elif change.startswith('reduce_to:'):
                parts = change.split(':')
                if len(parts) == 3:
                    ev_id = parts[1].strip()
                    val = float(parts[2].strip())
                    reduced_amounts[ev_id] = val

        # Variable burn savings from spending changes on flexible events
        burn_saving_per_day = 0.0
        rec_event_ids = {r['event_id'] for r in state.recurring_expenses}
        flex_by_id = {f['event_id']: f for f in state.flexible_events}

        for ev_id in stopped_event_ids:
            if ev_id not in rec_event_ids and ev_id in flex_by_id:
                burn_saving_per_day += flex_by_id[ev_id]['amount'] / 30.0

        for ev_id, red_amt in reduced_amounts.items():
            if ev_id not in rec_event_ids and ev_id in flex_by_id:
                saving = flex_by_id[ev_id]['amount'] - red_amt
                if saving > 0:
                    burn_saving_per_day += saving / 30.0

        effective_daily_burn = max(0.0, state.daily_variable_burn - burn_saving_per_day)

        # Simulation timeline initialization
        req_dt = pd.to_datetime(request_date)
        current_bal = state.liquid_starting_balance
        daily_records: List[Tuple[str, float]] = []

        sal_amt = state.salary_amount
        sal_day = state.salary_day_of_month if state.salary_day_of_month else 15
        next_sal_dt = state.next_salary_date

        for offset in range(horizon_days + 1):
            dt = req_dt + timedelta(days=offset)
            dt_str = dt.strftime('%Y-%m-%d')

            # 1. Salary Inflow (offset > 0, because offset 0 represents current liquid starting balance)
            if offset > 0 and sal_amt is not None and sal_amt > 0:
                is_sal = False
                if next_sal_dt and dt_str == next_sal_dt:
                    is_sal = True
                elif dt.day == sal_day:
                    is_sal = True
                
                if is_sal:
                    current_bal += sal_amt

            # 2. Outflow: Scheduled Debits
            if dt_str in state.scheduled_debits:
                current_bal -= state.scheduled_debits[dt_str]

            # 3. Outflow: Recurring Monthly Expenses
            for rec in state.recurring_expenses:
                ev_id = rec['event_id']
                if ev_id in stopped_event_ids:
                    continue

                amt = rec['amount']
                if ev_id in reduced_amounts:
                    amt = reduced_amounts[ev_id]

                # Apply on cadence interval or recurring day of month
                cadence = rec.get('cadence_days')
                last_dt = pd.to_datetime(rec['last_date'])
                if cadence and 14 <= cadence <= 27:
                    days_since = (dt - last_dt).days
                    if days_since > 0 and days_since % cadence == 0:
                        current_bal -= amt
                elif dt.day == rec['day_of_month']:
                    if offset == 0 and rec['last_date'] == dt_str:
                        # Already settled in starting balance
                        pass
                    elif dt > last_dt:
                        current_bal -= amt

            # 4. Outflow: Daily Variable Living Expenses Burn
            if offset > 0:
                current_bal -= effective_daily_burn

            # 5. Proposed Payments
            if dt_str in proposed_payments:
                current_bal -= proposed_payments[dt_str]

            daily_records.append((dt_str, current_bal))

        return daily_records

    def passes_safety_check(self, state: FinancialState, request_date: str,
                            proposed_payments: Optional[Dict[str, float]] = None,
                            spending_changes: Optional[List[str]] = None,
                            horizon_days: int = 90,
                            tolerance: float = 0.05) -> Tuple[bool, float]:
        """
        Verify whether balance >= minimum_balance_to_keep holds at every day in the forecast.

        Args:
            state: Reconstructed FinancialState.
            request_date: Evaluation date (YYYY-MM-DD).
            proposed_payments: Optional mapping of date to payment amount.
            spending_changes: Optional spending changes.
            horizon_days: Length of simulation window.
            tolerance: Float comparison tolerance for minor floating point rounding (default: 0.05).

        Returns:
            Tuple of (passes_check: bool, min_balance_seen: float).
        """
        daily_records = self.forecast_balance(
            state=state,
            request_date=request_date,
            proposed_payments=proposed_payments,
            spending_changes=spending_changes,
            horizon_days=horizon_days
        )

        min_bal = min(bal for _, bal in daily_records)
        is_safe = (min_bal >= state.minimum_balance_to_keep - tolerance)
        return is_safe, min_bal

    def simulate_schedule(self, state: FinancialState, request_date: str,
                          proposed_payments: Optional[Dict[str, float]] = None,
                          spending_changes: Optional[List[str]] = None,
                          horizon_days: int = 90) -> Tuple[float, bool, List[Tuple[str, float]]]:
        """
        Unified simulation helper returning (min_balance_seen, is_safe, daily_records).
        """
        daily_records = self.forecast_balance(
            state=state,
            request_date=request_date,
            proposed_payments=proposed_payments,
            spending_changes=spending_changes,
            horizon_days=horizon_days
        )
        min_bal = min(bal for _, bal in daily_records)
        is_safe = (min_bal >= state.minimum_balance_to_keep - 0.05)
        return min_bal, is_safe, daily_records
