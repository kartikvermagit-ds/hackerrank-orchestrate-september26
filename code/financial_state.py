from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from models import FinancialProfile, FinancialEvent

@dataclass
class FinancialState:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    reserved_pending_debits: float
    recurring_expenses: List[Dict]
    scheduled_debits: Dict[str, float]  # date_str -> amount
    daily_variable_burn: float
    salary_amount: Optional[float]
    salary_day_of_month: Optional[int]
    next_salary_date: Optional[str]
    protected_categories: Set[str]
    reducible_categories: Set[str]
    stoppable_categories: Set[str]
    allowed_payment_methods: Set[str]
    max_installment_months: Optional[float]
    daily_uncommitted_burn: float = 0.0
    flexible_events: List[Dict] = None

    def __post_init__(self):
        if self.flexible_events is None:
            self.flexible_events = []

    @property
    def liquid_starting_balance(self) -> float:
        """Starting balance after reserving pending debits."""
        return self.current_available_balance - self.reserved_pending_debits
