import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from models import Message

@dataclass
class SalaryUpdate:
    new_salary: Optional[float] = None
    currency: Optional[str] = None
    effective_date: Optional[str] = None
    revised_pay_date: Optional[str] = None
    contract_ended: bool = False
    unconfirmed_bonus: bool = False

class MessageProcessor:
    """Extracts factual updates and amendments from messages."""

    def __init__(self, messages: List[Message]):
        self.messages = messages
        self.user_messages: Dict[str, List[Message]] = {}
        for m in messages:
            self.user_messages.setdefault(m.user_id, []).append(m)

    def get_salary_update_for_user(self, user_id: str, request_date: str) -> Optional[SalaryUpdate]:
        msgs = self.user_messages.get(user_id, [])
        if not msgs:
            return None
        
        # Sort by sent_at
        sorted_msgs = sorted(msgs, key=lambda x: x.sent_at)
        update = SalaryUpdate()
        has_update = False

        for m in sorted_msgs:
            text = m.message_text

            # Check for contract end / no renewal
            if re.search(r'(current seasonal contract has ended|No off-season income or renewal has been confirmed)', text, re.IGNORECASE):
                update.contract_ended = True
                has_update = True

            # Check for unconfirmed bonus / commission
            if re.search(r'(belum disetujui|menunggu hasil akhir|not confirmed|pending final|unconfirmed)', text, re.IGNORECASE):
                update.unconfirmed_bonus = True

            # Check date revision: "confirmed salary is now expected on 2024-09-23. This replaces the payroll date"
            date_match = re.search(r'(expected on|credit date is|berlaku mulai)\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', text, re.IGNORECASE)
            if date_match:
                update.revised_pay_date = date_match.group(2)
                has_update = True

            # Check salary amount changes in English or Indonesian
            # Patterns:
            # "naik menjadi IDR 42750000"
            # "temporary monthly pay is EUR 1037.52"
            # "next salary is reduced to EUR 1422.85"
            # "monthly salary has increased to USD 2988"
            # "first salary will be EUR 1661"
            # "Regular salary of EUR 2717 resumes on"
            # "Gaji rutin Anda ... adalah IDR 21090000"
            # "Gaji pokok yang dikonfirmasi adalah IDR 38760000"
            amt_match = re.search(
                r'(?:naik menjadi|adalah|temporary monthly pay is|reduced to|increased to|first salary will be|Regular salary of)\s*([A-Z]{3})\s*([0-9]+(?:[\.,][0-9]+)?)',
                text, re.IGNORECASE
            )
            if amt_match and not update.unconfirmed_bonus:
                curr = amt_match.group(1).upper()
                amt_str = amt_match.group(2).replace(',', '')
                try:
                    update.new_salary = float(amt_str)
                    update.currency = curr
                    has_update = True
                except ValueError:
                    pass

        return update if has_update else None
