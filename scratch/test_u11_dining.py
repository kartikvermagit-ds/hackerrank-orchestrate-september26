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

# Include groceries, transport, dining in LIVING_EXPENSE_CATEGORIES
EventNormalizer.LIVING_EXPENSE_CATEGORIES = {'groceries', 'transport', 'dining'}

builder = ContextBuilder(profiles, events_by_user, payment_options, normalizer)
forecaster = ForecastEngine()

req11 = [x for x in samples if x.request_id == 'request_11'][0]
st11, _ = builder.build_context(req11)
print("Req 11 var burn with dining:", st11.daily_variable_burn)

for cand in ['2025-05-15', '2025-06-15', '2025-07-15']:
    rec = forecaster.forecast_balance(st11, req11.request_date, {cand: req11.requested_amount}, None, horizon_days=90)
    min_bal = min(b for _, b in rec)
    print(f"Paying on {cand}: min_bal = {min_bal:.1f} (diff: {min_bal - st11.minimum_balance_to_keep:.1f}) -> safe? {min_bal >= st11.minimum_balance_to_keep}")
