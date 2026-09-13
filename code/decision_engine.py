"""
Decision Engine Module
----------------------
Coordinates:
1. Headroom and earliest safe date calculation.
2. Candidate plan generation without spending changes.
3. Multi-tier candidate plan ranking:
   - Complete by desired_completion_date
   - Require no spending changes (fewer changes strictly preferred)
   - Minimize total amount paid
   - Start payment earlier
   - Use fewer payments
   - Lowest payment_option_id
4. Combinatorial flexible spending adjustments search when needed:
   - Only recurring flexible expenses in user-permitted categories
   - Never changes essential, fixed, one-time expenses, or unpermitted categories
   - Formats: stop:<event_id> and reduce_to:<event_id>:<amount>
   - Max 3 changes, mutual exclusivity enforced
5. Final RecommendationOutput formatting and explanation synthesis.
"""

import itertools
from typing import List, Dict, Tuple, Optional
import pandas as pd

from models import EvaluationRequest, PaymentOption, CandidatePlan, RecommendationOutput
from financial_state import FinancialState
from forecast import ForecastEngine
from safe_amount import SafeAmountCalculator
from payment_planner import PaymentPlanner

class DecisionEngine:
    """Multi-stage deterministic financial decision engine."""

    def __init__(self, forecast_engine: ForecastEngine,
                 safe_calc: SafeAmountCalculator,
                 planner: PaymentPlanner):
        self.forecaster = forecast_engine
        self.safe_calc = safe_calc
        self.planner = planner

    def find_best_spending_changes(self, request: EvaluationRequest,
                                   state: FinancialState,
                                   options: List[PaymentOption],
                                   amount_safe_to_pay: float,
                                   earliest_date_for_full_payment: Optional[str]) -> List[CandidatePlan]:
        """
        Explores combinations of up to 3 spending adjustments.

        Core Rules:
        - Only recurring expenses explicitly marked flexible and allowed by the user's profile may be changed.
        - Supported output formats:
            * stop:<event_id>
            * reduce_to:<event_id>:<new_amount>
        - Maximum 3 changes.
        - Stopping and reducing the same event are mutually exclusive.
        - Never change:
            * essential expenses (protected categories)
            * fixed expenses (flexibility == 'fixed')
            * one-time expenses
            * unsupported categories
            * events the user has not agreed to change
        - Search possible safe combinations deterministically.
        - Do not invent new expenses or reductions.
        """
        candidate_pool = list(state.recurring_expenses) + list(state.flexible_events)
        seen_events = set()
        candidate_changes: List[Tuple[str, float, str]] = []  # (action_str, monthly_saving, event_id)

        def fmt_amount(val: float) -> str:
            if float(val).is_integer():
                return f"{int(val)}"
            return f"{float(val):.2f}"

        for rec in candidate_pool:
            ev_id = rec['event_id']
            if ev_id in seen_events:
                continue
            seen_events.add(ev_id)

            cat = rec['category']
            flex = rec['flexibility']
            amt = rec['amount']
            min_amt = rec.get('minimum_allowed_amount')

            dt_str = str(rec.get('last_date') or rec.get('event_date') or '')
            dt_raw = pd.to_datetime(dt_str) if dt_str else req_dt
            day = rec.get('day_of_month') or dt_raw.day

            # Check next occurrence date
            req_dt = pd.to_datetime(request.request_date)
            try:
                next_occ = req_dt.replace(day=day)
            except ValueError:
                next_occ = req_dt.replace(day=28)
            if next_occ < req_dt:
                month = req_dt.month + 1 if req_dt.month < 12 else 1
                year = req_dt.year if req_dt.month < 12 else req_dt.year + 1
                try:
                    next_occ = pd.Timestamp(year=year, month=month, day=day)
                except ValueError:
                    next_occ = pd.Timestamp(year=year, month=month, day=28)
            next_occ_str = next_occ.strftime('%Y-%m-%d')
            if (next_occ - req_dt).days > 90:
                continue

            # 1. Never change essential or fixed expenses
            if cat in state.protected_categories or flex == 'fixed':
                continue

            # 2. Reducible action: when category is user-permitted to reduce and flex is reducible
            is_reducible = (cat in state.reducible_categories and flex in ['reducible', 'reducible_or_stoppable'] and min_amt is not None and amt > min_amt)
            if is_reducible:
                saving = amt - min_amt
                is_sub = 1 if ('subscription' in cat or 'cloud' in cat or 'streaming' in cat or rec.get('event_type') == 'subscription') else 0
                candidate_changes.append((f"reduce_to:{ev_id}:{fmt_amount(min_amt)}", saving, ev_id, dt_str, is_sub))

            # 3. Stoppable action: when category is user-permitted to stop
            can_stop = (cat in state.stoppable_categories and flex in ['stoppable', 'reducible_or_stoppable'])
            if can_stop:
                is_sub = 1 if ('subscription' in cat or 'cloud' in cat or 'streaming' in cat or rec.get('event_type') == 'subscription') else 0
                candidate_changes.append((f"stop:{ev_id}", amt, ev_id, dt_str, is_sub))

        # Deterministic ordering: prefer subscriptions, recency, saving, event_id
        candidate_changes.sort(key=lambda x: (x[4], x[3], x[1], x[2]), reverse=True)

        # Prune search space to top 8 actions to prevent combinatorial explosion
        pruned_candidates = [(c[0], c[1], c[2]) for c in candidate_changes[:8]]
        successful_plans: List[CandidatePlan] = []

        # Try combinations of size k = 1, then 2, then 3 (fewer changes strictly preferred)
        for k in range(1, min(4, len(pruned_candidates) + 1)):
            for combo_items in itertools.combinations(pruned_candidates, k):
                event_ids = [item[2] for item in combo_items]
                # Enforce mutual exclusivity on event_id
                if len(event_ids) != len(set(event_ids)):
                    continue

                combo_strings = sorted([item[0] for item in combo_items])
                plans = self.planner.generate_candidate_plans(
                    request=request,
                    state=state,
                    options=options,
                    amount_safe_to_pay=amount_safe_to_pay,
                    earliest_date_for_full_payment=earliest_date_for_full_payment,
                    spending_changes=combo_strings
                )
                safe_plans = [p for p in plans if p.is_safe]
                if safe_plans:
                    successful_plans.extend(safe_plans)

            if successful_plans:
                # Fewer changes is strictly prioritized per challenge rules
                break

        return successful_plans

    def rank_plans(self, plans: List[CandidatePlan], desired_completion_date: Optional[str] = None) -> List[CandidatePlan]:
        """
        Rank candidate plans per challenge tie-breaker rules:
        1. Complete by desired_completion_date
        2. Require no spending changes / fewer changes (len(spending_changes) asc)
        3. Minimize total amount paid (total_amount asc)
        4. Start payment earlier (first_payment_date asc)
        5. Use fewer payments (number_of_payments asc)
        6. Lowest payment_option_id (payment_option_id asc)
        """
        def sort_key(p: CandidatePlan):
            misses_deadline = False
            if desired_completion_date and p.payment_schedule:
                last_payment_date = p.payment_schedule[-1][0]
                misses_deadline = (last_payment_date > desired_completion_date)

            num_changes = len(p.spending_changes)
            tot_amt = round(p.total_amount, 2)
            first_date = p.first_payment_date if p.first_payment_date else "9999-99-99"
            num_payments = p.number_of_payments
            opt_id = p.payment_option_id if p.payment_option_id else "zzzzzz"
            return (misses_deadline, num_changes, tot_amt, first_date, num_payments, opt_id)

        return sorted(plans, key=sort_key)

    def generate_explanation(self, plan: CandidatePlan, request: EvaluationRequest,
                             state: FinancialState, amount_safe_to_pay: float) -> str:
        """
        Synthesize concise grounded explanation for the recommendation.
        """
        curr = state.home_currency
        min_bal_str = f"{curr} {state.minimum_balance_to_keep:,.2f}".replace('.00', '')
        req_amt_str = f"{curr} {request.requested_amount:,.2f}".replace('.00', '')

        if plan.method == 'full_payment':
            if not plan.spending_changes:
                return f"Pay {req_amt_str} today. This leaves at least {min_bal_str} available over the next 90 days."
            else:
                changes_text = []
                all_pool = list(state.recurring_expenses) + list(state.flexible_events)
                for ch in plan.spending_changes:
                    if ch.startswith('stop:'):
                        ev_id = ch.split(':')[1]
                        desc = next((r['description'].lower() for r in all_pool if r['event_id'] == ev_id), "subscription")
                        changes_text.append(f"Stop the {desc}")
                    elif ch.startswith('reduce_to:'):
                        parts = ch.split(':')
                        ev_id = parts[1]
                        val = float(parts[2])
                        val_str = f"{curr} {val:,.2f}".replace('.00', '')
                        desc = next((r['description'].lower() for r in all_pool if r['event_id'] == ev_id), "expense")
                        changes_text.append(f"reduce the {desc} to {val_str}")
                changes_str = " and ".join(changes_text)
                return f"{changes_str}, then pay {req_amt_str} today. This leaves at least {min_bal_str} available."

        elif plan.method == 'partial_payment':
            first_pay = plan.payment_schedule[0][1]
            second_pay = plan.payment_schedule[1][1]
            second_date = plan.payment_schedule[1][0]
            dt_obj = pd.to_datetime(second_date)
            date_formatted = dt_obj.strftime('%d %B %Y').lstrip('0')
            first_str = f"{curr} {first_pay:,.2f}".replace('.00', '')
            second_str = f"{curr} {second_pay:,.2f}".replace('.00', '')
            return f"Pay {first_str} today and the remaining {second_str} on {date_formatted}. This completes the full request and keeps the {min_bal_str} minimum protected."

        elif plan.method == 'installments':
            n = plan.number_of_payments
            inst_amt = plan.payment_schedule[0][1]
            inst_amt_str = f"{curr} {inst_amt:,.2f}".replace('.00', '')
            first_date = plan.first_payment_date
            dt_obj = pd.to_datetime(first_date)
            date_formatted = dt_obj.strftime('%d %B %Y').lstrip('0')
            return f"Use {n} installments of {inst_amt_str}, starting {date_formatted}. This leaves at least {min_bal_str} available."

        elif plan.method == 'wait':
            wait_date = plan.first_payment_date
            dt_obj = pd.to_datetime(wait_date)
            date_formatted = dt_obj.strftime('%d %B %Y').lstrip('0')
            return f"Pay {req_amt_str} in full on {date_formatted}. Paying earlier would take the balance below the {min_bal_str} minimum."

        else:  # not_recommended
            due_dt = pd.to_datetime(request.desired_completion_date)
            due_formatted = due_dt.strftime('%d %B %Y').lstrip('0')
            if amount_safe_to_pay > 0:
                safe_str = f"{curr} {amount_safe_to_pay:,.2f}".replace('.00', '')
                return f"Do not proceed with the {req_amt_str} request. Although {safe_str} is available today, the full amount cannot be completed safely within 90 days."
            return f"Do not make this payment by {due_formatted}. None of the available options keeps the {min_bal_str} minimum protected."

    def decide(self, request: EvaluationRequest, state: FinancialState,
               options: List[PaymentOption]) -> RecommendationOutput:
        """
        Determine the optimal financial recommendation for a user request.
        """
        # Step 1: Compute baseline safe amount & earliest safe date
        amount_safe = self.safe_calc.compute_safe_amount(
            state=state,
            request_date=request.request_date,
            requested_amount=request.requested_amount,
            desired_completion_date=request.desired_completion_date
        )
        earliest_date = self.safe_calc.compute_earliest_date_for_full_payment(
            state=state,
            request_date=request.request_date,
            requested_amount=request.requested_amount,
            amount_safe_to_pay=amount_safe,
            desired_completion_date=request.desired_completion_date
        )

        # Step 2: Generate candidate plans without spending changes
        plans_without_changes = self.planner.generate_candidate_plans(
            request=request,
            state=state,
            options=options,
            amount_safe_to_pay=amount_safe,
            earliest_date_for_full_payment=earliest_date,
            spending_changes=[]
        )
        safe_plans = [p for p in plans_without_changes if p.is_safe]

        # Step 3: Check for an eligible on-time plan without spending changes.
        # If none exists, search for safe plans with optional spending changes.
        deadline = request.desired_completion_date
        has_ontime_plan_without_changes = any(
            p.payment_schedule and (not deadline or p.payment_schedule[-1][0] <= deadline)
            for p in safe_plans
        )

        all_candidate_safe_plans = list(safe_plans)
        if not has_ontime_plan_without_changes:
            plans_with_changes = self.find_best_spending_changes(
                request=request,
                state=state,
                options=options,
                amount_safe_to_pay=amount_safe,
                earliest_date_for_full_payment=earliest_date
            )
            all_candidate_safe_plans.extend(plans_with_changes)

        winning_plan: Optional[CandidatePlan] = None
        if all_candidate_safe_plans:
            winning_plan = self.rank_plans(all_candidate_safe_plans, desired_completion_date=deadline)[0]

        # Step 4: Fallback to not_recommended if no viable plan
        if winning_plan is None:
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

        # Step 5: Format outputs matching exact challenge specifications
        plan_str = "none"
        if winning_plan.payment_schedule:
            def fmt_amt(val: float) -> str:
                if float(val).is_integer():
                    return f"{int(val)}"
                return f"{float(val):.2f}"
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
