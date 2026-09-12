from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

@dataclass
class FinancialProfile:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: List[str]
    expense_categories_to_protect: List[str]
    expense_categories_user_is_willing_to_reduce: List[str]
    expense_categories_user_is_willing_to_stop: List[str]
    payment_methods_user_will_consider: List[str]
    max_installment_months: Optional[float]

@dataclass
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str  # 'debit', 'credit', 'non_cash'
    amount: float
    currency: str
    event_date: str  # 'YYYY-MM-DD'
    settlement_date: str  # 'YYYY-MM-DD'
    status: str  # 'settled', 'pending', 'scheduled', 'cancelled', 'failed', 'unrealized'
    linked_event_id: Optional[str]
    flexibility: str  # 'fixed', 'reducible', 'stoppable', 'reducible_or_stoppable'
    minimum_allowed_amount: Optional[float]

@dataclass
class NormalizedEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str  # 'debit', 'credit', 'non_cash'
    original_amount: float
    original_currency: str
    normalized_amount: float  # In user's home_currency
    home_currency: str
    event_date: str  # YYYY-MM-DD
    settlement_date: str  # YYYY-MM-DD
    status: str  # 'settled', 'pending', 'scheduled', 'failed', 'cancelled', 'unrealized'
    linked_event_id: Optional[str]
    flexibility: str  # 'fixed', 'reducible', 'stoppable', 'reducible_or_stoppable'
    minimum_allowed_amount: Optional[float]  # Converted to home_currency
    classification: str  # 'settled_transaction', 'pending_debit', 'pending_credit', 'failed_transaction', 'cancelled_transaction', 'recurring_expense', 'confirmed_salary', 'recurring_income', 'refund', 'one_time_expense', 'transfer', 'investment', 'unrealized_investment', 'lifecycle_amendment'
    is_cash_flow_relevant: bool
    is_pending_debit: bool
    superseded_by: Optional[str] = None

@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str  # 'full_payment' or 'installments'
    payment_amount: float
    number_of_payments: int
    first_payment_date: str
    payment_frequency_days: Optional[float]
    financing_fee: float
    total_payable_amount: float

@dataclass
class Message:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: str
    source_type: str
    message_text: str

@dataclass
class EvaluationRequest:
    request_id: str
    user_id: str
    request_date: str
    request_type: str
    requested_amount: float
    desired_completion_date: str
    allows_partial_payment: bool
    request_text: str

@dataclass
class CandidatePlan:
    method: str  # 'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'
    payment_schedule: List[Tuple[str, float]]  # [(date_str, amount), ...]
    spending_changes: List[str]  # e.g. ['stop:event_1', 'reduce_to:event_2:100']
    total_amount: float
    first_payment_date: Optional[str]
    number_of_payments: int
    payment_option_id: Optional[str]
    is_safe: bool
    affordability_status: str  # 'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'
    earliest_date_for_full_payment: Optional[str]
    decision_explanation: str = ""

@dataclass
class RecommendationOutput:
    request_id: str
    amount_safe_to_pay: float
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str

@dataclass
class MessageEvidence:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: str
    source_type: str
    raw_text: str
    is_untrusted: bool = True

@dataclass
class ImageEvidence:
    image_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    file_path: str
    exists: bool
    is_untrusted: bool = True
    extracted_amount: Optional[float] = None

@dataclass
class EvidenceBundle:
    user_id: str
    request_id: Optional[str]
    user_messages: List[MessageEvidence]
    request_messages: List[MessageEvidence]
    event_messages: Dict[str, List[MessageEvidence]]
    request_images: List[ImageEvidence]
    event_images: Dict[str, List[ImageEvidence]]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize evidence bundle for downstream model consumption."""
        return {
            'user_id': self.user_id,
            'request_id': self.request_id,
            'user_messages': [
                {
                    'message_id': m.message_id,
                    'sent_at': m.sent_at,
                    'source_type': m.source_type,
                    'raw_text': m.raw_text,
                    'is_untrusted': m.is_untrusted
                } for m in self.user_messages
            ],
            'request_messages': [
                {
                    'message_id': m.message_id,
                    'sent_at': m.sent_at,
                    'source_type': m.source_type,
                    'raw_text': m.raw_text,
                    'is_untrusted': m.is_untrusted
                } for m in self.request_messages
            ],
            'event_messages': {
                ev_id: [
                    {
                        'message_id': m.message_id,
                        'sent_at': m.sent_at,
                        'source_type': m.source_type,
                        'raw_text': m.raw_text,
                        'is_untrusted': m.is_untrusted
                    } for m in m_list
                ] for ev_id, m_list in self.event_messages.items()
            },
            'request_images': [
                {
                    'image_id': img.image_id,
                    'file_path': img.file_path,
                    'exists': img.exists,
                    'is_untrusted': img.is_untrusted,
                    'extracted_amount': img.extracted_amount
                } for img in self.request_images
            ],
            'event_images': {
                ev_id: [
                    {
                        'image_id': img.image_id,
                        'file_path': img.file_path,
                        'exists': img.exists,
                        'is_untrusted': img.is_untrusted,
                        'extracted_amount': img.extracted_amount
                    } for img in img_list
                ] for ev_id, img_list in self.event_images.items()
            }
        }

