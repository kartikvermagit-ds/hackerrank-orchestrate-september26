import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from safe_amount import SafeAmountCalculator
from forecast import ForecastEngine

loader = DataLoader('dataset')
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
profiles = loader.load_profiles()
events_by_user = loader.load_events()
payment_options = loader.load_payment_options()
messages = loader.load_messages()
samples = loader.load_requests('sample_requests.csv')
sample_df = pd.read_csv('dataset/sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_conv, msg_proc)

# Test 60-day burn
def calc_var_60(self, events, request_date, recurring_categories=None):
    req_dt = pd.to_datetime(request_date)
    start_60 = req_dt - pd.Timedelta(days=60)
    start_30 = req_dt - pd.Timedelta(days=30)
    debits_60 = []
    debits_30 = []
    for e in events:
        if (e.status == 'settled' and e.direction == 'debit' and e.category in self.LIVING_EXPENSE_CATEGORIES):
            dt = pd.to_datetime(e.event_date)
            desc_lower = e.description.lower()
            if 'bulk' in desc_lower and 'purchase' in desc_lower:
                continue
            if start_60 <= dt < req_dt:
                debits_60.append(e.amount)
            if start_30 <= dt < req_dt:
                debits_30.append(e.amount)
    burn_60 = sum(debits_60) / 60.0 if debits_60 else 0.0
    burn_30 = sum(debits_30) / 30.0 if debits_30 else 0.0
    return burn_60 if burn_60 > 0 else burn_30

normalizer.calculate_variable_daily_burn = calc_var_60.__get__(normalizer, EventNormalizer)

builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()
safe_calc = SafeAmountCalculator(forecaster)

# Check request 17
req17 = [x for x in samples if x.request_id == 'request_17'][0]
st17, _ = builder.build_context(req17)
print("Req 17 var burn:", st17.daily_variable_burn)
safe_u17, min_u17 = forecaster.passes_safety_check(st17, req17.request_date, {'2026-03-15': 274600.0}, None, 90)
print(f"Req 17 paying on 2026-03-15 with 60d burn: safe={safe_u17}, min_bal={min_u17:.2f}, diff={min_u17 - st17.minimum_balance_to_keep:.2f}")
