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

req11 = [r for r in samples if r.request_id == 'request_11'][0]
state11, opts11 = builder.build_context(req11)

target = 16880550.0
print(f"Target expense deduction = {target}")

# List recurring expenses and their sums
rec_sum = sum(r['amount'] for r in state11.recurring_expenses)
print(f"Total recurring expenses (1 month) = {rec_sum}")
print(f"Target - rec_sum = {target - rec_sum}")

# What if 12 days to payday (May 3 to May 15)?
# Debits before May 15:
# Housing: May 5: 2954500
# Utilities: May 8: 2796165.18
# Insurance: May 9: 1881000
# Education: May 10: 2544100
# Healthcare: May 12: 2826901.92
# Cloud storage: May 14: 168150
debits_before_may15 = 2954500 + 2796165.18 + 1881000 + 2544100 + 2826901.92 + 168150
print(f"Debits before May 15 = {debits_before_may15}")
print(f"Target - debits_before_may15 = {target - debits_before_may15}")
print(f"Per day for 12 days = {(target - debits_before_may15) / 12}")
print(f"Daily uncommitted burn = {state11.daily_uncommitted_burn}")
print(f"Daily var burn = {state11.daily_variable_burn}")
