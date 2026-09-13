import sys
sys.path.insert(0, 'code')
import pandas as pd
from loader import DataLoader
from event_normalizer import EventNormalizer
from message_processor import MessageProcessor
from context_builder import ContextBuilder

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

req21 = [r for r in samples if r.request_id == 'request_21'][0]
state21, opts21 = builder.build_context(req21)

print("User 21 Recurring Expenses:")
for r in state21.recurring_expenses:
    print(r)

print("\nUser 21 Scheduled Debits:", state21.scheduled_debits)
print("User 21 Daily var burn:", state21.daily_variable_burn)
print("User 21 Daily uncommitted burn:", state21.daily_uncommitted_burn)
