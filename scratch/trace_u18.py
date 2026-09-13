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

req18 = [r for r in samples if r.request_id == 'request_18'][0]
state18, opts18 = builder.build_context(req18)

print(f"User 18 Start Balance: {state18.liquid_starting_balance}, Min: {state18.minimum_balance_to_keep}")
print(f"Salary: {state18.salary_amount}, day: {state18.salary_day_of_month}")
print(f"Daily Var Burn: {state18.daily_variable_burn}, Uncommitted Burn: {state18.daily_uncommitted_burn}")
print(f"Recurring expenses: {state18.recurring_expenses}")

print("\n--- Simulating payment of 3246.10 on 2026-08-15 ---")
records = forecaster.forecast_balance(state18, req18.request_date, {'2026-08-15': 3246.10}, None, 90)
for dt_str, bal in records:
    if '2026-08-14' <= dt_str <= '2026-08-16' or '2026-09-13' <= dt_str <= '2026-09-16':
        print(f"  {dt_str}: balance = {bal:.2f} (diff from min: {bal - state18.minimum_balance_to_keep:.2f})")
is_safe, min_bal = forecaster.passes_safety_check(state18, req18.request_date, {'2026-08-15': 3246.10}, None, 90)
print(f"Safety 90d from req_date: safe={is_safe}, min_bal={min_bal:.2f}")

print("\n--- What if evaluated 90d from payment date (2026-08-15 to 2026-11-15)? ---")
# But wait, what if evaluated until the complete safety horizon?
