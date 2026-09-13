from typing import Dict, List, Optional, Tuple, Set
from models import FinancialProfile, FinancialEvent, PaymentOption, EvaluationRequest, Message
from financial_state import FinancialState
from event_normalizer import EventNormalizer
import pandas as pd

class ContextBuilder:
    def __init__(self, profiles: Dict[str, FinancialProfile],
                 events_by_user: Dict[str, List[FinancialEvent]],
                 payment_options_by_req: Dict[str, List[PaymentOption]],
                 event_normalizer: EventNormalizer):
        self.profiles = profiles
        self.events_by_user = events_by_user
        self.payment_options_by_req = payment_options_by_req
        self.normalizer = event_normalizer

    def build_context(self, request: EvaluationRequest) -> Tuple[FinancialState, List[PaymentOption]]:
        u_id = request.user_id
        profile = self.profiles[u_id]
        raw_events = self.events_by_user.get(u_id, [])
        options = self.payment_options_by_req.get(request.request_id, [])

        # Normalize events
        norm_events = self.normalizer.normalize_events_for_user(raw_events, profile.home_currency)

        # Reserved pending debits on or before request_date
        reserved_debits = 0.0
        for e in norm_events:
            if e.status == 'pending' and e.direction == 'debit' and e.event_date <= request.request_date:
                reserved_debits += e.amount

        # Extract recurring monthly expenses
        recurring_expenses = self.normalizer.extract_recurring_monthly_expenses(norm_events, request.request_date)
        recurring_cats = {r['category'] for r in recurring_expenses}
        # Fixed monthly categories
        recurring_cats.update(['rent', 'utilities', 'debt_repayment', 'insurance', 'subscription', 'education', 'housing', 'cloud_storage', 'streaming', 'music_subscription', 'delivery_membership', 'gym', 'entertainment', 'healthcare', 'family_support', 'shopping'])

        # Calculate variable burn
        daily_var_burn = self.normalizer.calculate_variable_daily_burn(norm_events, request.request_date, recurring_cats)

        # Calculate uncommitted living burn (groceries, transport, dining) for short-term pre-payday protection
        req_dt = pd.to_datetime(request.request_date)
        start_60 = req_dt - pd.Timedelta(days=60)
        start_30 = req_dt - pd.Timedelta(days=30)
        liv_60 = [e.amount for e in norm_events if e.status == 'settled' and e.direction == 'debit' and e.category in {'groceries', 'transport', 'dining'} and start_60 <= pd.to_datetime(e.event_date) < req_dt]
        liv_30 = [e.amount for e in norm_events if e.status == 'settled' and e.direction == 'debit' and e.category in {'groceries', 'transport', 'dining'} and start_30 <= pd.to_datetime(e.event_date) < req_dt]
        burn_uncommitted = max(sum(liv_60)/60.0 if liv_60 else 0.0, sum(liv_30)/30.0 if liv_30 else 0.0)
        if burn_uncommitted == 0.0:
            burn_uncommitted = daily_var_burn

        # Extract scheduled future debits
        scheduled_debits = {}
        for e in norm_events:
            if e.status == 'scheduled' and e.direction == 'debit':
                d_str = e.settlement_date if e.settlement_date else e.event_date
                if d_str >= request.request_date:
                    scheduled_debits[d_str] = scheduled_debits.get(d_str, 0.0) + e.amount

        # Extract salary details
        sal_amt, sal_day, next_sal_date = self.normalizer.get_salary_info(u_id, norm_events, request.request_date)

        # Extract active flexible candidate events from recent cycle (within 45 days of request_date)
        flex_map = {}
        cutoff_dt = (pd.to_datetime(request.request_date) - pd.Timedelta(days=45)).strftime('%Y-%m-%d')
        for e in sorted(norm_events, key=lambda x: x.event_date):
            if e.status == 'settled' and e.direction == 'debit' and cutoff_dt <= e.event_date < request.request_date:
                if e.flexibility in ['stoppable', 'reducible', 'reducible_or_stoppable']:
                    flex_map[e.description] = {
                        'event_id': e.event_id,
                        'category': e.category,
                        'description': e.description,
                        'flexibility': e.flexibility,
                        'amount': e.amount,
                        'minimum_allowed_amount': e.minimum_allowed_amount,
                        'event_date': e.event_date
                    }
        flexible_events = list(flex_map.values())

        state = FinancialState(
            user_id=u_id,
            home_currency=profile.home_currency,
            current_available_balance=profile.current_available_balance,
            minimum_balance_to_keep=profile.minimum_balance_to_keep,
            reserved_pending_debits=reserved_debits,
            recurring_expenses=recurring_expenses,
            scheduled_debits=scheduled_debits,
            daily_variable_burn=daily_var_burn,
            salary_amount=sal_amt,
            salary_day_of_month=sal_day,
            next_salary_date=next_sal_date,
            protected_categories=set(profile.expense_categories_to_protect),
            reducible_categories=set(profile.expense_categories_user_is_willing_to_reduce),
            stoppable_categories=set(profile.expense_categories_user_is_willing_to_stop),
            allowed_payment_methods=set(profile.payment_methods_user_will_consider),
            max_installment_months=profile.max_installment_months,
            daily_uncommitted_burn=burn_uncommitted,
            flexible_events=flexible_events
        )

        return state, options
