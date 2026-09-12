"""
Data Loading & Validation Layer
--------------------------------
Ingests all tabular datasets from the dataset/ directory using pandas.
Performs:
- File existence verification with clear error messages.
- Strict schema/column presence validation.
- Consistent date parsing and ISO-8601 formatting.
- Numerical precision preservation (float64/int64).
- Clean entity mapping to typed domain models.
- Read-only data access with zero modification of input files.
"""

import os
from typing import Dict, List, Optional, Tuple, Set
import pandas as pd
import numpy as np

from models import (
    FinancialProfile,
    FinancialEvent,
    PaymentOption,
    Message,
    EvaluationRequest
)
from currency import CurrencyConverter
from image_processor import ImageProcessor

class DataLoader:
    """Loads and validates all dataset CSV files from dataset/ directory."""

    REQUIRED_FILES = {
        'financial_profiles.csv',
        'financial_events.csv',
        'exchange_rates.csv',
        'request_payment_options.csv',
        'messages.csv',
        'images.csv'
    }

    REQUIRED_COLUMNS = {
        'financial_profiles.csv': [
            'user_id', 'home_currency', 'current_available_balance', 'minimum_balance_to_keep',
            'financial_priorities', 'expense_categories_to_protect',
            'expense_categories_user_is_willing_to_reduce', 'expense_categories_user_is_willing_to_stop',
            'payment_methods_user_will_consider', 'max_installment_months'
        ],
        'financial_events.csv': [
            'event_id', 'user_id', 'event_type', 'description', 'category', 'direction',
            'amount', 'currency', 'event_date', 'settlement_date', 'status',
            'linked_event_id', 'flexibility', 'minimum_allowed_amount'
        ],
        'exchange_rates.csv': [
            'rate_date', 'from_currency', 'to_currency', 'rate'
        ],
        'request_payment_options.csv': [
            'payment_option_id', 'request_id', 'payment_method', 'payment_amount',
            'number_of_payments', 'first_payment_date', 'payment_frequency_days',
            'financing_fee', 'total_payable_amount'
        ],
        'messages.csv': [
            'message_id', 'user_id', 'request_id', 'related_event_id', 'sent_at',
            'source_type', 'message_text'
        ],
        'images.csv': [
            'image_id', 'user_id', 'request_id', 'related_event_id'
        ],
        'requests.csv': [
            'request_id', 'user_id', 'request_date', 'request_type', 'requested_amount',
            'desired_completion_date', 'allows_partial_payment', 'request_text'
        ]
    }

    def __init__(self, dataset_dir: str = 'dataset'):
        self.dataset_dir = dataset_dir
        if not os.path.isdir(self.dataset_dir):
            raise FileNotFoundError(f"Dataset directory not found: '{self.dataset_dir}'")
        self.currency_converter: Optional[CurrencyConverter] = None
        self.image_processor: Optional[ImageProcessor] = None

    def _get_file_path(self, filename: str) -> str:
        """Resolve and verify existence of a required file."""
        path = os.path.join(self.dataset_dir, filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Required dataset file missing: '{path}'")
        return path

    def _read_and_validate_csv(self, filename: str) -> pd.DataFrame:
        """Read CSV with pandas and validate required columns."""
        path = self._get_file_path(filename)
        df = pd.read_csv(path)

        req_cols = self.REQUIRED_COLUMNS.get(filename)
        if req_cols:
            missing = [col for col in req_cols if col not in df.columns]
            if missing:
                raise ValueError(
                    f"File '{filename}' is missing required columns: {missing}. Found: {list(df.columns)}"
                )
        return df

    def _parse_date(self, val: object) -> str:
        """Parse date value to consistent YYYY-MM-DD string format."""
        if pd.isna(val):
            return ""
        s = str(val).strip()
        try:
            return pd.to_datetime(s).strftime('%Y-%m-%d')
        except Exception:
            return s

    def load_exchange_rates(self) -> CurrencyConverter:
        """Load exchange rates table and initialize CurrencyConverter."""
        df = self._read_and_validate_csv('exchange_rates.csv')
        df['rate_date'] = df['rate_date'].apply(self._parse_date)
        df['rate'] = df['rate'].astype(float)
        self.currency_converter = CurrencyConverter(df)
        return self.currency_converter

    def load_images(self) -> ImageProcessor:
        """Load images mapping and initialize ImageProcessor."""
        path = os.path.join(self.dataset_dir, 'images.csv')
        media_dir = os.path.join(self.dataset_dir, 'media', 'images')
        df = self._read_and_validate_csv('images.csv') if os.path.exists(path) else None
        self.image_processor = ImageProcessor(df, media_dir)
        return self.image_processor

    def load_profiles(self) -> Dict[str, FinancialProfile]:
        """Load user financial profiles into domain dataclasses."""
        df = self._read_and_validate_csv('financial_profiles.csv')
        profiles: Dict[str, FinancialProfile] = {}

        for _, r in df.iterrows():
            def parse_pipe(val):
                if pd.isna(val):
                    return []
                return [s.strip() for s in str(val).split('|') if s.strip()]

            u_id = str(r['user_id']).strip()
            max_inst = None if pd.isna(r.get('max_installment_months')) else float(r['max_installment_months'])

            p = FinancialProfile(
                user_id=u_id,
                home_currency=str(r['home_currency']).strip(),
                current_available_balance=float(r['current_available_balance']),
                minimum_balance_to_keep=float(r['minimum_balance_to_keep']),
                financial_priorities=parse_pipe(r.get('financial_priorities')),
                expense_categories_to_protect=parse_pipe(r.get('expense_categories_to_protect')),
                expense_categories_user_is_willing_to_reduce=parse_pipe(r.get('expense_categories_user_is_willing_to_reduce')),
                expense_categories_user_is_willing_to_stop=parse_pipe(r.get('expense_categories_user_is_willing_to_stop')),
                payment_methods_user_will_consider=parse_pipe(r.get('payment_methods_user_will_consider')),
                max_installment_months=max_inst
            )
            profiles[u_id] = p
        return profiles

    def load_events(self) -> Dict[str, List[FinancialEvent]]:
        """Load historical, pending, and scheduled financial events grouped by user_id."""
        df = self._read_and_validate_csv('financial_events.csv')
        events_by_user: Dict[str, List[FinancialEvent]] = {}

        for r in df.to_dict('records'):
            ev_id = str(r['event_id']).strip()
            u_id = str(r['user_id']).strip()

            # Amount resolution from receipt/invoice image when blank
            amt = r.get('amount')
            if pd.isna(amt):
                if self.image_processor:
                    resolved = self.image_processor.get_amount_for_event(ev_id)
                    amt = resolved if resolved is not None else 0.0
                else:
                    amt = 0.0
            else:
                amt = float(amt)

            linked = None if pd.isna(r.get('linked_event_id')) else str(r['linked_event_id']).strip()
            min_amt = None if pd.isna(r.get('minimum_allowed_amount')) else float(r['minimum_allowed_amount'])
            
            ev_date = self._parse_date(r.get('event_date'))
            settle_date = self._parse_date(r.get('settlement_date')) if pd.notna(r.get('settlement_date')) else ev_date

            ev = FinancialEvent(
                event_id=ev_id,
                user_id=u_id,
                event_type=str(r['event_type']).strip(),
                description=str(r['description']).strip(),
                category=str(r['category']).strip(),
                direction=str(r['direction']).strip(),
                amount=amt,
                currency=str(r['currency']).strip(),
                event_date=ev_date,
                settlement_date=settle_date,
                status=str(r['status']).strip(),
                linked_event_id=linked,
                flexibility=str(r['flexibility']).strip(),
                minimum_allowed_amount=min_amt
            )
            events_by_user.setdefault(u_id, []).append(ev)
        return events_by_user

    def load_payment_options(self) -> Dict[str, List[PaymentOption]]:
        """Load request payment options grouped by request_id."""
        df = self._read_and_validate_csv('request_payment_options.csv')
        opts_by_req: Dict[str, List[PaymentOption]] = {}

        for _, r in df.iterrows():
            req_id = str(r['request_id']).strip()
            freq = None if pd.isna(r.get('payment_frequency_days')) else float(r['payment_frequency_days'])
            first_date = self._parse_date(r.get('first_payment_date'))

            opt = PaymentOption(
                payment_option_id=str(r['payment_option_id']).strip(),
                request_id=req_id,
                payment_method=str(r['payment_method']).strip(),
                payment_amount=float(r['payment_amount']),
                number_of_payments=int(r['number_of_payments']),
                first_payment_date=first_date,
                payment_frequency_days=freq,
                financing_fee=float(r['financing_fee']),
                total_payable_amount=float(r['total_payable_amount'])
            )
            opts_by_req.setdefault(req_id, []).append(opt)
        return opts_by_req

    def load_messages(self) -> List[Message]:
        """Load communication messages."""
        df = self._read_and_validate_csv('messages.csv')
        msgs: List[Message] = []

        for _, r in df.iterrows():
            req_id = None if pd.isna(r.get('request_id')) else str(r['request_id']).strip()
            ev_id = None if pd.isna(r.get('related_event_id')) else str(r['related_event_id']).strip()

            m = Message(
                message_id=str(r['message_id']).strip(),
                user_id=str(r['user_id']).strip(),
                request_id=req_id,
                related_event_id=ev_id,
                sent_at=str(r['sent_at']).strip(),
                source_type=str(r['source_type']).strip(),
                message_text=str(r['message_text']).strip()
            )
            msgs.append(m)
        return msgs

    def load_requests(self, filename: str = 'requests.csv') -> List[EvaluationRequest]:
        """Load evaluation requests."""
        df = self._read_and_validate_csv(filename)
        reqs: List[EvaluationRequest] = []

        for _, r in df.iterrows():
            req = EvaluationRequest(
                request_id=str(r['request_id']).strip(),
                user_id=str(r['user_id']).strip(),
                request_date=self._parse_date(r.get('request_date')),
                request_type=str(r['request_type']).strip(),
                requested_amount=float(r['requested_amount']),
                desired_completion_date=self._parse_date(r.get('desired_completion_date')),
                allows_partial_payment=bool(r['allows_partial_payment']),
                request_text=str(r['request_text']).strip()
            )
            reqs.append(req)
        return reqs
