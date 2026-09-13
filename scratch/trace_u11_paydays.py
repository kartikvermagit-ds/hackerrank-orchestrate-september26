import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder
from forecast import ForecastEngine

loader = DataLoader('dataset')
currency_conv = loader.load_exchange_rates()
img_proc = loader.load_images()
profiles = loader.load_profiles()
events_by_user = loader.load_events()
payment_options = loader.load_payment_options()
messages = loader.load_messages()
samples = loader.load_requests('sample_requests.csv')

msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_conv, msg_proc)
builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()

req11 = [r for r in samples if r.request_id == 'request_11'][0]
state11, opts11 = builder.build_context(req11)

print(f"User 11 start balance: {state11.liquid_starting_balance}")
print(f"Min balance: {state11.minimum_balance_to_keep}")
print(f"Salary: {state11.salary_amount}")

# Check paying 13,110,000 on 2025-05-15, 2025-06-15, 2025-07-15
for cand in ['2025-05-15', '2025-06-15', '2025-07-15']:
    rec = forecaster.forecast_balance(state11, req11.request_date, {cand: req11.requested_amount}, None, horizon_days=90)
    min_bal = min(b for _, b in rec)
    print(f"Paying on {cand}: min_bal = {min_bal} (diff: {min_bal - state11.minimum_balance_to_keep}) -> safe? {min_bal >= state11.minimum_balance_to_keep}")
