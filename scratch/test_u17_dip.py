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

req17 = [r for r in samples if r.request_id == 'request_17'][0]
state17, opts17 = builder.build_context(req17)

# User 17: paying 274600 on 2026-03-15
# Check balance day by day
records = forecaster.forecast_balance(state17, req17.request_date, {'2026-03-15': 274600.0}, None, horizon_days=90)
for dt, bal in records:
    diff = bal - state17.minimum_balance_to_keep
    if diff < 0:
        print(f"Dipped on {dt}: bal={bal:.1f}, diff={diff:.1f}")
