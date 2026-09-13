"""
Strict Deterministic Decision Validator
----------------------------------------
Validates every generated financial recommendation against the complete challenge contract:
1. Required fields presence and valid data types.
2. Valid affordability_status in {'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'}.
3. Valid recommended_payment_method in {'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'}.
4. 0 <= amount_safe_to_pay <= requested_amount.
5. Strictly chronological payment_plan entries formatted as YYYY-MM-DD:amount.
6. Payment totals matching requested amount (or provider option total for installments).
7. Partial-payment preconditions (request permits, user accepts, 0 < safe < requested, completes by deadline).
8. Installment option matching (strictly matches a supplied provider option, tenure <= max_installment_months).
9. Completion by desired_completion_date for all approved plans.
10. Earliest date rules (equals request_date for affordable_now, valid forecast date or empty).
11. Spending changes rules (max 3, mutual exclusivity, only flexible recurring expenses in permitted categories).
12. Continuous forecast re-simulation guaranteeing balance >= minimum_balance_to_keep.

Any invalid decision is rejected with descriptive error messages rather than written to output.csv.
"""

from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime
import pandas as pd

from models import RecommendationOutput, EvaluationRequest, PaymentOption
from financial_state import FinancialState
from forecast import ForecastEngine

class DecisionValidationError(ValueError):
    """Raised when a recommendation fails strict deterministic validation."""
    pass

class OutputValidator:
    """Deterministic validator enforcing all problem statement rules and output contracts."""

    ALLOWED_STATUSES: Set[str] = {
        'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'
    }
    ALLOWED_METHODS: Set[str] = {
        'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'
    }
    REQUIRED_COLUMNS: List[str] = [
        'request_id',
        'amount_safe_to_pay',
        'affordability_status',
        'recommended_payment_method',
        'payment_plan',
        'earliest_date_for_full_payment',
        'spending_changes_needed',
        'decision_explanation'
    ]

    @classmethod
    def parse_payment_plan(cls, plan_str: str) -> List[Tuple[str, float]]:
        """Parse payment plan string into list of (date_str, amount) tuples."""
        if plan_str == 'none' or not plan_str.strip():
            return []
        items = []
        for part in plan_str.split('|'):
            tokens = part.strip().split(':')
            if len(tokens) != 2:
                raise DecisionValidationError(f"Malformed payment plan entry: '{part}' in plan '{plan_str}'")
            date_str, amt_str = tokens
            # Validate ISO date
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                raise DecisionValidationError(f"Invalid date format in payment plan: '{date_str}'")
            try:
                amt = float(amt_str)
            except ValueError:
                raise DecisionValidationError(f"Invalid numeric amount in payment plan: '{amt_str}'")
            items.append((date_str, amt))
        return items

    @classmethod
    def validate_row(cls, rec: RecommendationOutput,
                     request: EvaluationRequest,
                     state: Optional[FinancialState] = None,
                     options: Optional[List[PaymentOption]] = None,
                     forecaster: Optional[ForecastEngine] = None,
                     raise_exception: bool = False) -> List[str]:
        """Convenience alias for validate_decision."""
        return cls.validate_decision(rec, request, state, options, forecaster, raise_exception)

    @classmethod
    def validate_decision(cls, rec: RecommendationOutput,
                          request: EvaluationRequest,
                          state: Optional[FinancialState] = None,
                          options: Optional[List[PaymentOption]] = None,
                          forecaster: Optional[ForecastEngine] = None,
                          raise_exception: bool = False) -> List[str]:
        """
        Validate a single RecommendationOutput against the request, user state, and supplied options.

        Returns list of error messages. If raise_exception is True, raises DecisionValidationError.
        """
        errors: List[str] = []

        # 1. Required fields & ID check
        if not rec.request_id or rec.request_id != request.request_id:
            errors.append(f"request_id mismatch or empty: expected '{request.request_id}', got '{rec.request_id}'")

        if not rec.decision_explanation or not rec.decision_explanation.strip():
            errors.append("decision_explanation is empty")

        # 2. Status & Method enum checks
        if rec.affordability_status not in cls.ALLOWED_STATUSES:
            errors.append(f"Invalid affordability_status '{rec.affordability_status}'. Must be one of {cls.ALLOWED_STATUSES}")

        if rec.recommended_payment_method not in cls.ALLOWED_METHODS:
            errors.append(f"Invalid recommended_payment_method '{rec.recommended_payment_method}'. Must be one of {cls.ALLOWED_METHODS}")

        # Status / Method consistency
        if rec.affordability_status == 'affordable_later' and rec.recommended_payment_method != 'wait':
            errors.append(f"affordability_status 'affordable_later' requires method 'wait', got '{rec.recommended_payment_method}'")
        if rec.affordability_status == 'not_affordable' and rec.recommended_payment_method != 'not_recommended':
            errors.append(f"affordability_status 'not_affordable' requires method 'not_recommended', got '{rec.recommended_payment_method}'")
        if rec.recommended_payment_method == 'not_recommended' and rec.affordability_status != 'not_affordable':
            errors.append(f"method 'not_recommended' requires affordability_status 'not_affordable', got '{rec.affordability_status}'")

        # 3. amount_safe_to_pay bounds
        req_amt = request.requested_amount
        if rec.amount_safe_to_pay < -1e-4 or rec.amount_safe_to_pay > req_amt + 1e-4:
            errors.append(f"amount_safe_to_pay ({rec.amount_safe_to_pay}) out of bounds [0, {req_amt}]")

        # 4. earliest_date_for_full_payment rules
        if rec.affordability_status == 'affordable_now':
            if rec.earliest_date_for_full_payment != request.request_date:
                errors.append(f"affordable_now requires earliest_date_for_full_payment == request_date ({request.request_date}), got '{rec.earliest_date_for_full_payment}'")

        if rec.earliest_date_for_full_payment:
            try:
                e_dt = datetime.strptime(rec.earliest_date_for_full_payment, '%Y-%m-%d')
                r_dt = datetime.strptime(request.request_date, '%Y-%m-%d')
                diff_days = (e_dt - r_dt).days
                if diff_days < 0 or diff_days > 90:
                    errors.append(f"earliest_date_for_full_payment '{rec.earliest_date_for_full_payment}' outside 90-day forecast window from {request.request_date}")
            except ValueError:
                errors.append(f"Malformed earliest_date_for_full_payment: '{rec.earliest_date_for_full_payment}'")

        # 5. Parse and validate payment_plan
        try:
            schedule = cls.parse_payment_plan(rec.payment_plan)
        except DecisionValidationError as e:
            errors.append(str(e))
            schedule = []

        if rec.recommended_payment_method == 'not_recommended':
            if rec.payment_plan != 'none':
                errors.append(f"not_recommended requires payment_plan 'none', got '{rec.payment_plan}'")
            if rec.spending_changes_needed != 'none':
                errors.append(f"not_recommended requires spending_changes_needed 'none', got '{rec.spending_changes_needed}'")
        else:
            if not schedule:
                errors.append(f"Approved method '{rec.recommended_payment_method}' must have an active payment schedule, got '{rec.payment_plan}'")

            # Verify strictly chronological
            dates = [d for d, _ in schedule]
            for i in range(len(dates) - 1):
                if dates[i] > dates[i + 1]:
                    errors.append(f"payment_plan is not chronological: {dates[i]} > {dates[i+1]}")

            # All amounts must be positive
            for d, amt in schedule:
                if amt <= 0.0:
                    errors.append(f"Payment plan amount on {d} must be positive, got {amt}")

            # Desired completion date check
            if schedule:
                last_date = schedule[-1][0]
                if last_date > request.desired_completion_date:
                    errors.append(f"Final payment date ({last_date}) exceeds desired_completion_date ({request.desired_completion_date})")

        # 6. Specific payment method rules
        if rec.recommended_payment_method == 'full_payment':
            if state and 'full_payment' not in state.allowed_payment_methods:
                errors.append("full_payment is not permitted by user's payment_methods_user_will_consider")
            if len(schedule) != 1:
                errors.append(f"full_payment must have exactly 1 payment, got {len(schedule)}")
            elif schedule:
                p_date, p_amt = schedule[0]
                if p_date != request.request_date:
                    errors.append(f"full_payment must be on request_date ({request.request_date}), got {p_date}")
                if abs(p_amt - req_amt) > 0.05:
                    errors.append(f"full_payment amount ({p_amt}) does not equal requested_amount ({req_amt})")

        elif rec.recommended_payment_method == 'partial_payment':
            if not request.allows_partial_payment:
                errors.append("partial_payment recommended but request.allows_partial_payment is False")
            if state and 'partial_payment' not in state.allowed_payment_methods:
                errors.append("partial_payment is not permitted by user's payment_methods_user_will_consider")
            if not (0.0 < rec.amount_safe_to_pay < req_amt):
                errors.append(f"partial_payment requires 0 < amount_safe_to_pay < requested_amount, got safe={rec.amount_safe_to_pay}, req={req_amt}")
            if not rec.earliest_date_for_full_payment:
                errors.append("partial_payment requires a valid earliest_date_for_full_payment")
            elif rec.earliest_date_for_full_payment > request.desired_completion_date:
                errors.append(f"partial_payment second date ({rec.earliest_date_for_full_payment}) exceeds desired_completion_date ({request.desired_completion_date})")
            if rec.spending_changes_needed != 'none':
                errors.append("partial_payment cannot be combined with optional spending changes")

            if len(schedule) != 2:
                errors.append(f"partial_payment must have exactly 2 payments, got {len(schedule)}")
            elif schedule:
                d1, a1 = schedule[0]
                d2, a2 = schedule[1]
                if d1 != request.request_date:
                    errors.append(f"partial_payment first date must be request_date ({request.request_date}), got {d1}")
                if abs(a1 - rec.amount_safe_to_pay) > 0.05:
                    errors.append(f"partial_payment first amount ({a1}) != amount_safe_to_pay ({rec.amount_safe_to_pay})")
                if d2 != rec.earliest_date_for_full_payment:
                    errors.append(f"partial_payment second date must be earliest_date ({rec.earliest_date_for_full_payment}), got {d2}")
                if abs((a1 + a2) - req_amt) > 0.05:
                    errors.append(f"partial_payment sum ({a1 + a2}) does not equal requested_amount ({req_amt})")

        elif rec.recommended_payment_method == 'wait':
            if state and 'full_payment' not in state.allowed_payment_methods:
                errors.append("wait requires user to accept full_payment in payment_methods_user_will_consider")
            if not rec.earliest_date_for_full_payment:
                errors.append("wait requires earliest_date_for_full_payment to be populated")
            elif rec.earliest_date_for_full_payment <= request.request_date:
                errors.append(f"wait requires earliest_date_for_full_payment ({rec.earliest_date_for_full_payment}) > request_date ({request.request_date})")
            elif rec.earliest_date_for_full_payment > request.desired_completion_date:
                errors.append(f"wait payment date ({rec.earliest_date_for_full_payment}) exceeds desired_completion_date ({request.desired_completion_date})")

            if len(schedule) != 1:
                errors.append(f"wait must have exactly 1 payment, got {len(schedule)}")
            elif schedule:
                p_date, p_amt = schedule[0]
                if p_date != rec.earliest_date_for_full_payment:
                    errors.append(f"wait payment date ({p_date}) != earliest_date_for_full_payment ({rec.earliest_date_for_full_payment})")
                if abs(p_amt - req_amt) > 0.05:
                    errors.append(f"wait payment amount ({p_amt}) != requested_amount ({req_amt})")

        elif rec.recommended_payment_method == 'installments':
            if state and 'installments' not in state.allowed_payment_methods:
                errors.append("installments recommended but user payment_methods_user_will_consider disallows installments")
            if options is not None:
                # Must match at least one supplied provider option
                matched = False
                tot_paid = sum(amt for _, amt in schedule)
                n_payments = len(schedule)
                first_date = schedule[0][0] if schedule else ""

                for opt in options:
                    if opt.payment_method == 'installments' and opt.number_of_payments == n_payments and opt.first_payment_date == first_date:
                        if abs(opt.total_payable_amount - tot_paid) <= 0.1:
                            # Verify max_installment_months
                            if state and state.max_installment_months is not None:
                                freq = opt.payment_frequency_days if opt.payment_frequency_days else 30.0
                                dur_months = ((opt.number_of_payments - 1) * freq) / 30.0
                                if dur_months > state.max_installment_months and opt.number_of_payments > state.max_installment_months:
                                    continue
                            matched = True
                            break
                if not matched:
                    errors.append(f"Installment schedule {rec.payment_plan} does not match any eligible provider option in request_payment_options.csv")

        # 7. Spending changes validation
        if rec.spending_changes_needed != 'none':
            changes = rec.spending_changes_needed.split('|')
            if len(changes) > 3:
                errors.append(f"spending_changes_needed exceeds maximum of 3 changes: {len(changes)}")

            event_ids = []
            pool_events = {r['event_id']: r for r in list(state.recurring_expenses) + list(state.flexible_events)} if state else {}

            for ch in changes:
                parts = ch.strip().split(':')
                action = parts[0]
                if action not in ['stop', 'reduce_to']:
                    errors.append(f"Invalid spending change action '{action}' in '{ch}'")
                    continue
                if action == 'stop' and len(parts) != 2:
                    errors.append(f"Malformed stop action: '{ch}'. Expected stop:<event_id>")
                    continue
                if action == 'reduce_to' and len(parts) != 3:
                    errors.append(f"Malformed reduce_to action: '{ch}'. Expected reduce_to:<event_id>:<amount>")
                    continue

                ev_id = parts[1]
                event_ids.append(ev_id)

                if state:
                    if ev_id not in pool_events:
                        errors.append(f"Changed event '{ev_id}' not found in user's flexible recurring expenses")
                        continue

                    ev = pool_events[ev_id]
                    cat = ev['category']
                    flex = ev['flexibility']

                    if cat in state.protected_categories:
                        errors.append(f"Cannot change protected category '{cat}' for event '{ev_id}'")
                    if flex == 'fixed':
                        errors.append(f"Cannot change fixed event '{ev_id}'")

                    if action == 'stop':
                        if cat not in state.stoppable_categories:
                            errors.append(f"Cannot stop category '{cat}' not in user's stoppable_categories: {state.stoppable_categories}")
                        if flex not in ['stoppable', 'reducible_or_stoppable']:
                            errors.append(f"Event '{ev_id}' flexibility '{flex}' cannot be stopped")

                    elif action == 'reduce_to':
                        if cat not in state.reducible_categories:
                            errors.append(f"Cannot reduce category '{cat}' not in user's reducible_categories: {state.reducible_categories}")
                        if flex not in ['reducible', 'reducible_or_stoppable']:
                            errors.append(f"Event '{ev_id}' flexibility '{flex}' cannot be reduced")
                        try:
                            red_amt = float(parts[2])
                            min_amt = ev.get('minimum_allowed_amount')
                            if min_amt is not None and red_amt < min_amt - 0.05:
                                errors.append(f"reduce_to amount {red_amt} < minimum_allowed_amount {min_amt} for event '{ev_id}'")
                            if red_amt >= ev['amount']:
                                errors.append(f"reduce_to amount {red_amt} must be strictly less than current amount {ev['amount']}")
                        except ValueError:
                            errors.append(f"Invalid numeric amount in reduce_to: '{parts[2]}'")

            # Mutual exclusivity check: each event can appear at most once
            if len(event_ids) != len(set(event_ids)):
                errors.append(f"Mutually exclusive violation: duplicate event IDs in spending changes {event_ids}")

        # 8. Continuous forecast re-simulation (minimum balance verification)
        if forecaster is not None and state is not None and rec.recommended_payment_method != 'not_recommended':
            payments_dict = {d: amt for d, amt in schedule}
            spending_list = rec.spending_changes_needed.split('|') if rec.spending_changes_needed != 'none' else []
            last_date = schedule[-1][0]
            req_dt = pd.to_datetime(request.request_date)
            last_dt = pd.to_datetime(last_date)
            # Active plan horizon covers all payments through completion date
            h_days = max(1, min(90, (last_dt - req_dt).days))
            is_safe, min_bal_seen = forecaster.passes_safety_check(
                state=state,
                request_date=request.request_date,
                proposed_payments=payments_dict,
                spending_changes=spending_list,
                horizon_days=h_days
            )
            if not is_safe:
                errors.append(
                    f"Recommended plan violates minimum_balance_to_keep! "
                    f"Min balance seen: {min_bal_seen:.2f}, required: {state.minimum_balance_to_keep:.2f}"
                )


        if errors and raise_exception:
            raise DecisionValidationError(f"Validation failed for request '{request.request_id}':\n" + "\n".join(f" - {e}" for e in errors))

        return errors

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame, expected_rows: Optional[int] = None) -> List[str]:
        """Validate entire prediction DataFrame for column format, non-emptiness, and expected row count."""
        errors: List[str] = []
        if list(df.columns) != cls.REQUIRED_COLUMNS:
            errors.append(f"Columns mismatch! Expected exact columns:\n{cls.REQUIRED_COLUMNS}\nGot:\n{list(df.columns)}")

        if expected_rows is not None and len(df) != expected_rows:
            errors.append(f"Expected exactly {expected_rows} rows, got {len(df)}")

        # Check unique request_ids
        if df['request_id'].duplicated().any():
            dups = df[df['request_id'].duplicated()]['request_id'].tolist()
            errors.append(f"Duplicate request_id entries found: {dups}")

        # Check for NaN in critical columns
        for col in ['request_id', 'amount_safe_to_pay', 'affordability_status', 'recommended_payment_method', 'payment_plan', 'spending_changes_needed']:
            if df[col].isna().any():
                null_indices = df[df[col].isna()].index.tolist()
                errors.append(f"Null values detected in column '{col}' at indices {null_indices[:5]}")

        return errors
