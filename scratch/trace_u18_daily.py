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
requests = loader.load_requests('sample_requests.csv')
msg_proc = MessageProcessor(messages)
normalizer = EventNormalizer(currency_converter=currency_conv, message_processor=msg_proc)
context_builder = ContextBuilder(profiles=profiles, events_by_user=events_by_user, payment_options_by_req=payment_options, event_normalizer=normalizer)
forecaster = ForecastEngine()

r18 = [r for r in requests if r.request_id == 'request_18'][0]
state, _ = context_builder.build_context(r18)
records = forecaster.forecast_balance(state, r18.request_date, proposed_payments={'2026-08-15': 3246.10}, horizon_days=90)
for d, b in records:
    if '2026-08-10' <= d <= '2026-09-16':
        print(f"  {d}: {b:.2f}")
