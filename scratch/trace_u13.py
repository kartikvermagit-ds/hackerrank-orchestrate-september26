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

req13 = [r for r in samples if r.request_id == 'request_13'][0]
state13, opts13 = builder.build_context(req13)

print(f"User 13 Start Balance: {state13.liquid_starting_balance}, Min: {state13.minimum_balance_to_keep}")
print(f"Salary: {state13.salary_amount}, day: {state13.salary_day_of_month}")
print(f"Daily Var Burn: {state13.daily_variable_burn}, Uncommitted Burn: {state13.daily_uncommitted_burn}")
print(f"Recurring expenses: {state13.recurring_expenses}")

print("\n--- Simulating payment of 941.60 on 2024-05-15 ---")
records = forecaster.forecast_balance(state13, req13.request_date, {'2024-05-15': 941.60}, None, 90)
for dt_str, bal in records:
    if bal < state13.minimum_balance_to_keep + 50:
        print(f"  {dt_str}: balance = {bal:.2f} (diff from min: {bal - state13.minimum_balance_to_keep:.2f})")
is_safe, min_bal = forecaster.passes_safety_check(state13, req13.request_date, {'2024-05-15': 941.60}, None, 90)
print(f"Safety 90d from req_date: safe={is_safe}, min_bal={min_bal:.2f}")
