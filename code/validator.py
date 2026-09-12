from typing import List, Dict, Tuple
import pandas as pd
from models import RecommendationOutput, EvaluationRequest

class OutputValidator:
    ALLOWED_STATUSES = {'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'}
    ALLOWED_METHODS = {'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'}
    REQUIRED_COLUMNS = [
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
    def validate_row(cls, rec: RecommendationOutput, request: EvaluationRequest) -> List[str]:
        errors = []

        # Bound check
        if not (0 <= rec.amount_safe_to_pay <= request.requested_amount + 1e-5):
            errors.append(f"amount_safe_to_pay ({rec.amount_safe_to_pay}) out of bounds [0, {request.requested_amount}]")

        # Allowed values
        if rec.affordability_status not in cls.ALLOWED_STATUSES:
            errors.append(f"Invalid affordability_status: {rec.affordability_status}")
        if rec.recommended_payment_method not in cls.ALLOWED_METHODS:
            errors.append(f"Invalid recommended_payment_method: {rec.recommended_payment_method}")

        # Affordable now constraint
        if rec.affordability_status == 'affordable_now':
            if rec.earliest_date_for_full_payment != request.request_date:
                errors.append(f"affordable_now must have earliest_date == request_date ({request.request_date}), got {rec.earliest_date_for_full_payment}")

        # Partial payment check
        if rec.recommended_payment_method == 'partial_payment':
            parts = rec.payment_plan.split('|')
            if len(parts) != 2:
                errors.append(f"partial_payment must have exactly 2 payments, got {len(parts)}")
            else:
                amt1 = float(parts[0].split(':')[1])
                amt2 = float(parts[1].split(':')[1])
                if abs((amt1 + amt2) - request.requested_amount) > 0.05:
                    errors.append(f"partial_payment sum {amt1 + amt2} != requested {request.requested_amount}")

        # Spending changes check
        if rec.spending_changes_needed != 'none':
            changes = rec.spending_changes_needed.split('|')
            if len(changes) > 3:
                errors.append(f"spending_changes_needed exceeds max 3 items: {len(changes)}")
            event_ids = [c.split(':')[1] for c in changes if ':' in c]
            if len(event_ids) != len(set(event_ids)):
                errors.append(f"spending_changes_needed contains duplicate event IDs: {changes}")

        return errors

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> List[str]:
        errors = []
        if list(df.columns) != cls.REQUIRED_COLUMNS:
            errors.append(f"Columns mismatch! Expected {cls.REQUIRED_COLUMNS}, got {list(df.columns)}")
        if len(df) != 250:
            errors.append(f"Expected exactly 250 rows for requests.csv evaluation, got {len(df)}")
        return errors
