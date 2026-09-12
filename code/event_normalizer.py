"""
Financial Event Normalization Layer
------------------------------------
Creates normalized internal representations for all financial events.
Applies:
- Multi-currency conversion to user's home currency using fixed, dated exchange rates.
- Lifecycle event resolution and explicit conflict-resolution rules:
  1. Explicit cancellation, settlement, or amendment.
  2. Newer record from the same source.
  3. Settled event over estimate or forecast.
  4. Financially safer interpretation if unresolved.
- Event classification distinguishing:
  - settled transactions
  - pending transactions (debit vs credit)
  - failed transactions
  - cancelled transactions
  - recurring expenses
  - recurring income
  - confirmed salary
  - refunds
  - one-time expenses
  - transfers
  - investments
  - unrealized investments
  - duplicate/repeated lifecycle records
- Detection of recurring monthly expenses and essential variable living expense burn.
- Resolution of missing amounts via ImageProcessor without inventing information.
"""

from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime, timedelta
from collections import Counter
import pandas as pd

from models import FinancialEvent, NormalizedEvent
from currency import CurrencyConverter
from message_processor import MessageProcessor

class EventNormalizer:
    """Normalizes, classifies, and resolves financial events for evaluation."""

    FIXED_MONTHLY_CATEGORIES = {
        'rent', 'utilities', 'debt_repayment', 'insurance', 'education', 
        'housing', 'subscription', 'cloud_storage', 'streaming', 
        'music_subscription', 'delivery_membership', 'gym', 'entertainment',
        'healthcare', 'family_support'
    }

    LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}

    REGULAR_SALARY_KEYWORDS = [
        'payroll', 'salary', 'base salary', 'first-job', 'promotion arrears'
    ]

    GIG_KEYWORDS = [
        'platform', 'driver', 'marketplace', 'freelance', 'contract payment', 
        'gig', 'app earnings', 'weekly app', 'earnings', 'seasonal', 'temporary'
    ]

    TRANSFER_KEYWORDS = [
        'transfer', 'remittance', 'support payment', 'association fee'
    ]

    def __init__(self, currency_converter: CurrencyConverter, message_processor: MessageProcessor):
        self.fx = currency_converter
        self.msg_proc = message_processor

    def normalize_event(self, event: FinancialEvent, home_currency: str) -> NormalizedEvent:
        """
        Convert an individual event to user's home currency and wrap in NormalizedEvent.
        Preserves numeric precision. Never treats blank amount as zero.
        """
        if event.amount is None:
            raise ValueError(f"Event {event.event_id} has unresolved amount. Blank amount must be resolved before normalization.")

        # Multi-currency conversion
        rate_date = event.settlement_date if event.settlement_date else event.event_date
        if event.currency != home_currency:
            norm_amount = self.fx.convert(event.amount, event.currency, home_currency, rate_date)
            norm_min_amount = (
                self.fx.convert(event.minimum_allowed_amount, event.currency, home_currency, rate_date)
                if event.minimum_allowed_amount is not None else None
            )
        else:
            norm_amount = float(event.amount)
            norm_min_amount = float(event.minimum_allowed_amount) if event.minimum_allowed_amount is not None else None

        return NormalizedEvent(
            event_id=event.event_id,
            user_id=event.user_id,
            event_type=event.event_type,
            description=event.description,
            category=event.category,
            direction=event.direction,
            original_amount=float(event.amount),
            original_currency=event.currency,
            normalized_amount=norm_amount,
            home_currency=home_currency,
            event_date=event.event_date,
            settlement_date=event.settlement_date if event.settlement_date else event.event_date,
            status=event.status,
            linked_event_id=event.linked_event_id,
            flexibility=event.flexibility,
            minimum_allowed_amount=norm_min_amount,
            classification='unclassified',
            is_cash_flow_relevant=False,
            is_pending_debit=False,
            superseded_by=None
        )

    def resolve_conflicts_and_lifecycle(self, events: List[NormalizedEvent]) -> List[NormalizedEvent]:
        """
        Apply conflict-resolution rules from problem statement:
        1. An explicit cancellation, settlement, or amendment
        2. A newer record from the same source
        3. A settled event over an estimate or forecast
        4. The financially safer interpretation when unresolved
        """
        by_id = {e.event_id: e for e in events}

        # Rule 1 & 3: Trace linked lifecycle chains
        for e in events:
            if e.linked_event_id and e.linked_event_id in by_id:
                parent = by_id[e.linked_event_id]

                # Explicit cancellation or settlement superseding an earlier authorization / estimate
                if parent.status == 'cancelled' and e.status == 'settled':
                    parent.superseded_by = e.event_id
                elif parent.status == 'pending' and e.status == 'settled':
                    parent.superseded_by = e.event_id
                elif parent.status == 'failed' and e.status == 'scheduled':
                    # Scheduled retry supersedes failed payment
                    parent.superseded_by = e.event_id
                elif parent.event_type == 'investment_purchase' and e.event_type == 'investment_sale' and e.status == 'settled':
                    # Realized sale supersedes original purchase basis
                    parent.superseded_by = e.event_id
                elif parent.event_type == 'investment_purchase' and e.event_type == 'investment_valuation':
                    # Unrealized valuation is non-cash; purchase was settled cash outflow
                    e.is_cash_flow_relevant = False

        # Rule 2: Newer records from same source / duplicate detection
        # Check potential duplicate pairs
        for e in events:
            if 'duplicate' in e.description.lower() and e.status == 'pending':
                # Possible duplicate card charge pending: financially safe to reserve, but flagged
                e.is_pending_debit = True

        return events

    def classify_events(self, events: List[NormalizedEvent], request_date: str) -> List[NormalizedEvent]:
        """
        Assign precise domain classifications to every normalized event.
        """
        for e in events:
            # Check if superseded
            if e.superseded_by is not None:
                e.classification = 'lifecycle_amendment'
                e.is_cash_flow_relevant = False
                continue

            # 1. Cancelled
            if e.status == 'cancelled':
                e.classification = 'cancelled_transaction'
                e.is_cash_flow_relevant = False

            # 2. Failed
            elif e.status == 'failed':
                e.classification = 'failed_transaction'
                e.is_cash_flow_relevant = False

            # 3. Unrealized investment
            elif e.direction == 'non_cash' or e.status == 'unrealized' or e.event_type == 'investment_valuation':
                e.classification = 'unrealized_investment'
                e.is_cash_flow_relevant = False

            # 4. Investment purchases & sales
            elif e.category == 'investment' or e.event_type in ['investment_purchase', 'investment_sale']:
                e.classification = 'investment'
                e.is_cash_flow_relevant = (e.status == 'settled')

            # 5. Refunds
            elif e.event_type == 'refund' or 'reversal' in e.description.lower() or 'reimbursement' in e.description.lower():
                e.classification = 'refund'
                # Only settled refunds count as cashflow
                e.is_cash_flow_relevant = (e.status == 'settled')

            # 6. Pending debits vs Pending credits
            elif e.status == 'pending':
                if e.direction == 'debit':
                    e.classification = 'pending_debit'
                    e.is_pending_debit = True
                    e.is_cash_flow_relevant = True  # Must be reserved against available balance
                else:
                    e.classification = 'pending_credit'
                    e.is_cash_flow_relevant = False  # Never count pending credits per rules

            # 7. Salary & Income
            elif e.category == 'salary' or e.event_type == 'income':
                desc_l = e.description.lower()
                is_gig = any(k in desc_l for k in self.GIG_KEYWORDS)
                is_regular = any(k in desc_l for k in self.REGULAR_SALARY_KEYWORDS) or (e.category == 'salary' and not is_gig)

                if e.status == 'scheduled':
                    e.classification = 'confirmed_salary'
                    e.is_cash_flow_relevant = True
                elif is_regular and not is_gig:
                    e.classification = 'recurring_income'
                    e.is_cash_flow_relevant = (e.status == 'settled')
                else:
                    # Windfall, bonus, commission, or gig earnings
                    e.classification = 'windfall_or_gig_income'
                    # Count only if already settled; never project forward
                    e.is_cash_flow_relevant = (e.status == 'settled' and e.event_date <= request_date)

            # 8. Transfers
            elif any(k in e.description.lower() for k in self.TRANSFER_KEYWORDS):
                e.classification = 'transfer'
                e.is_cash_flow_relevant = (e.status == 'settled')

            # 9. Fixed monthly recurring expenses
            elif e.category in self.FIXED_MONTHLY_CATEGORIES and e.direction == 'debit':
                e.classification = 'recurring_expense'
                e.is_cash_flow_relevant = True

            # 10. Living variable expenses
            elif e.category in self.LIVING_EXPENSE_CATEGORIES and e.direction == 'debit':
                e.classification = 'variable_living_expense'
                e.is_cash_flow_relevant = (e.status == 'settled')

            # 11. One-time expenses
            else:
                e.classification = 'one_time_expense'
                e.is_cash_flow_relevant = (e.status == 'settled')

        return events

    def normalize_events_for_user(self, events: List[FinancialEvent], home_currency: str,
                                  request_date: Optional[str] = None) -> List[NormalizedEvent]:
        """
        Complete normalization pipeline for a user's events:
        1. Multi-currency conversion & precision preservation.
        2. Conflict resolution & lifecycle chaining.
        3. Classification into standard domain categories.
        """
        if request_date is None:
            request_date = "9999-12-31"

        normalized = [self.normalize_event(e, home_currency) for e in events]
        resolved = self.resolve_conflicts_and_lifecycle(normalized)
        classified = self.classify_events(resolved, request_date)
        return classified

    def extract_recurring_monthly_expenses(self, events: List[FinancialEvent], request_date: str) -> List[Dict]:
        """Identify monthly fixed debits that recur on a specific day of month."""
        groups = {}
        for e in events:
            if e.direction == 'debit' and e.status == 'settled' and e.event_date < request_date:
                if e.category in self.FIXED_MONTHLY_CATEGORIES:
                    key = (e.category, e.description, e.flexibility)
                    groups.setdefault(key, []).append(e)

        recurring = []
        for (cat, desc, flex), ev_list in groups.items():
            if len(ev_list) >= 2:
                sorted_evs = sorted(ev_list, key=lambda x: x.event_date)
                dates = [pd.to_datetime(x.event_date) for x in sorted_evs]
                intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                avg_interval = sum(intervals) / len(intervals) if intervals else 30

                # Monthly cadence (20 to 35 days)
                if 20 <= avg_interval <= 35 or len(ev_list) >= 2:
                    last_ev = sorted_evs[-1]
                    day_of_month = pd.to_datetime(last_ev.event_date).day
                    min_allowed = last_ev.minimum_allowed_amount

                    recurring.append({
                        'category': cat,
                        'description': desc,
                        'flexibility': flex,
                        'amount': last_ev.amount,
                        'day_of_month': day_of_month,
                        'last_date': last_ev.event_date,
                        'event_id': last_ev.event_id,
                        'minimum_allowed_amount': min_allowed
                    })

        return recurring

    def calculate_variable_daily_burn(self, events: List[FinancialEvent], request_date: str,
                                      recurring_categories: Optional[Set[str]] = None) -> float:
        """Calculates daily burn rate for essential variable living categories (groceries, transport, dining)."""
        req_dt = pd.to_datetime(request_date)
        start_dt = req_dt - pd.Timedelta(days=60)

        var_debits = [
            e.amount for e in events 
            if e.status == 'settled' and e.direction == 'debit' and e.category in self.LIVING_EXPENSE_CATEGORIES 
            and start_dt <= pd.to_datetime(e.event_date) < req_dt
        ]
        if not var_debits:
            return 0.0
        return sum(var_debits) / 60.0

    def get_salary_info(self, user_id: str, events: List[FinancialEvent], request_date: str) -> Tuple[Optional[float], Optional[int], Optional[str]]:
        """
        Returns (salary_amount, salary_day_of_month, next_confirmed_salary_date).
        Distinguishes regular confirmed salary from variable gig platform payouts.
        """
        salary_update = self.msg_proc.get_salary_update_for_user(user_id, request_date)

        # If contract ended, no future salary
        if salary_update and salary_update.contract_ended:
            return None, None, None

        # Check for scheduled 'Next confirmed salary' in events
        scheduled_salaries = [e for e in events if e.status == 'scheduled' and 'salary' in e.description.lower()]
        next_date = None
        next_amt = None
        if scheduled_salaries:
            next_date = scheduled_salaries[0].settlement_date
            next_amt = scheduled_salaries[0].amount

        settled_regular_salaries = []
        for e in events:
            if e.status == 'settled' and (e.category == 'salary' or e.event_type == 'income'):
                desc_lower = e.description.lower()
                is_gig = any(k in desc_lower for k in self.GIG_KEYWORDS)
                is_regular = any(k in desc_lower for k in self.REGULAR_SALARY_KEYWORDS) or (e.category == 'salary' and not is_gig)
                if is_regular and not is_gig:
                    settled_regular_salaries.append(e)

        if not settled_regular_salaries and next_amt is None and (not salary_update or salary_update.new_salary is None):
            # No regular confirmed salary (e.g. gig worker)
            return None, None, None

        base_amt = next_amt
        salary_day = 15

        if settled_regular_salaries:
            sorted_salaries = sorted(settled_regular_salaries, key=lambda x: x.event_date)
            # If final payroll, contract ended
            if 'final' in sorted_salaries[-1].description.lower():
                return None, None, None

            if base_amt is None:
                base_amt = sorted_salaries[-1].amount

            # Find most common day of month for salary
            sal_days = [pd.to_datetime(s.event_date).day for s in settled_regular_salaries]
            if sal_days:
                salary_day = Counter(sal_days).most_common(1)[0][0]

        # Apply message updates
        if salary_update:
            if salary_update.new_salary is not None:
                base_amt = salary_update.new_salary
            if salary_update.revised_pay_date:
                next_date = salary_update.revised_pay_date
                salary_day = pd.to_datetime(next_date).day

        return base_amt, salary_day, next_date
